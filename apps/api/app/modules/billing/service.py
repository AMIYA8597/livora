"""
Subscription lifecycle on Razorpay.

Checkout: `start_checkout` creates (or reuses) a Razorpay subscription for the plan and returns
its id for Razorpay Checkout. After payment the browser posts the handler fields to `verify`,
which checks the signature and then reads the subscription from Razorpay: the client is never
trusted for status or dates.

Webhooks (`handle_webhook`) are the source of truth for everything after that: renewals,
failed charges, halts, cancellations. Each delivery is signature-checked, stored once in
`billing_events` (Razorpay retries, so duplicates are normal) and applied only if it is newer
than the last event applied to that subscription.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.modules.billing.entitlements import (
    active_listing_count,
    featured_listing_count,
    get_entitlements,
    likes_today,
    live_subscription_filter,
    next_reset_utc,
)
from app.modules.billing.razorpay import (
    RazorpayClient,
    RazorpayError,
    billing_enabled,
    verify_subscription_payment_signature,
    verify_webhook_signature,
)
from app.modules.properties.models import Property
from app.modules.subscriptions.models import BillingEvent, Payment, Subscription, SubscriptionPlan
from app.modules.users.models import User

logger = logging.getLogger("flatmate.billing")

# Billing cycles before a Razorpay subscription completes (5 years monthly). Users can cancel
# any time; this only bounds the mandate.
TOTAL_CYCLES = 60
OPEN_STATUSES = ("created", "authenticated", "active", "pending")
_SUB_ID = re.compile(r"^sub_[A-Za-z0-9]{6,40}$")
_PAY_ID = re.compile(r"^pay_[A-Za-z0-9]{6,40}$")

# Shown to the user (in-app) when Razorpay reports these.
_NOTIFY = {
    "subscription.activated": ("Your plan is active", "Thanks for subscribing to {plan}. Your new features are ready."),
    "subscription.pending": ("Payment didn't go through", "We couldn't renew {plan}. Razorpay will retry; check your payment method."),
    "subscription.halted": ("Your plan is paused", "Renewing {plan} failed several times. Subscribe again to keep its features."),
    "subscription.cancelled": ("Your plan was cancelled", "{plan} won't renew. You keep its features until the paid period ends."),
}


def _require_billing() -> None:
    if not billing_enabled():
        raise ServiceUnavailableException("Paid plans aren't available yet.", error_code="BILLING_DISABLED")


def _ts(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None
    except (TypeError, ValueError, OSError):
        return None


def _paise(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


@dataclass
class CheckoutSession:
    subscription_id: str
    key_id: str
    plan_code: str
    plan_name: str
    amount_inr: Decimal
    prefill: Dict[str, str]


class BillingService:
    def __init__(self, db: AsyncSession, client: Optional[RazorpayClient] = None):
        self.db = db
        self.client = client or RazorpayClient()

    # ------------------------------------------------------------------------------ catalogue

    async def list_plans(self) -> List[SubscriptionPlan]:
        return list((await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.price_inr)
        )).scalars().all())

    async def _provider_plan_id(self, plan: SubscriptionPlan) -> str:
        """Razorpay plans are immutable: create one the first time, and again after a price change."""
        amount = _paise(plan.price_inr)
        if plan.razorpay_plan_id and plan.razorpay_plan_amount == amount:
            return plan.razorpay_plan_id
        locked = (await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan.id).with_for_update()
        )).scalar_one()
        if locked.razorpay_plan_id and locked.razorpay_plan_amount == amount:
            return locked.razorpay_plan_id
        created = await self.client.create_plan(
            name=locked.name, amount_paise=amount, period=locked.period, interval=locked.interval,
            description=locked.description or "", notes={"plan_code": locked.code},
        )
        locked.razorpay_plan_id = created["id"]
        locked.razorpay_plan_amount = amount
        await self.db.flush()
        return locked.razorpay_plan_id

    # ------------------------------------------------------------------------------ checkout

    async def start_checkout(self, user: User, plan_code: str) -> CheckoutSession:
        _require_billing()
        plan = (await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code, SubscriptionPlan.is_active.is_(True))
        )).scalar_one_or_none()
        if plan is None:
            raise NotFoundException("That plan isn't available.")

        open_sub = (await self.db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id, Subscription.plan_id == plan.id,
                Subscription.status.in_(OPEN_STATUSES),
            )
        )).scalar_one_or_none()
        if open_sub is not None and open_sub.status != "created":
            raise ConflictException(f"You already have {plan.name}.", error_code="ALREADY_SUBSCRIBED")

        try:
            if open_sub is not None and open_sub.provider_subscription_id:
                # An unfinished checkout: reuse it rather than leave orphans at Razorpay.
                provider_id = open_sub.provider_subscription_id
            else:
                provider_plan = await self._provider_plan_id(plan)
                created = await self.client.create_subscription(
                    plan_id=provider_plan, total_count=TOTAL_CYCLES,
                    notes={"user_id": str(user.id), "plan_code": plan.code},
                )
                provider_id = created["id"]
                open_sub = Subscription(
                    user_id=user.id, plan_id=plan.id, status=created.get("status") or "created",
                    provider="razorpay", provider_subscription_id=provider_id,
                    short_url=created.get("short_url"),
                )
                self.db.add(open_sub)
            await self.db.commit()
        except RazorpayError as exc:
            await self.db.rollback()
            raise ServiceUnavailableException("Couldn't start the payment. Please try again.") from exc

        return CheckoutSession(
            subscription_id=provider_id, key_id=settings.RAZORPAY_KEY_ID or "", plan_code=plan.code,
            plan_name=plan.name, amount_inr=plan.price_inr,
            prefill={"name": user.full_name or "", "email": user.email or ""},
        )

    async def verify(self, user: User, payment_id: str, subscription_id: str, signature: str) -> Subscription:
        """Checkout handler callback. The signature proves the payment came from our checkout;
        the status and paid period come from Razorpay itself."""
        _require_billing()
        if not (_SUB_ID.match(subscription_id or "") and _PAY_ID.match(payment_id or "")):
            raise BadRequestException("Invalid payment reference.")
        if not verify_subscription_payment_signature(payment_id, subscription_id, signature):
            raise BadRequestException("We couldn't verify this payment.", error_code="INVALID_SIGNATURE")
        sub = (await self.db.execute(
            select(Subscription).where(Subscription.provider_subscription_id == subscription_id)
        )).scalar_one_or_none()
        if sub is None or sub.user_id != user.id:
            raise NotFoundException("Subscription not found.")
        try:
            entity = await self.client.fetch_subscription(subscription_id)
        except RazorpayError as exc:
            raise ServiceUnavailableException("Payment received; we'll confirm it shortly.") from exc
        self._apply_entity(sub, entity)
        if sub.expires_at is None and sub.status in ("authenticated", "active"):
            # Paid, but Razorpay hasn't set the period yet: a short grant until the
            # subscription.charged webhook sets the real end.
            sub.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def cancel(self, user: User, subscription_uuid: UUID) -> Subscription:
        _require_billing()
        sub = await self.db.get(Subscription, subscription_uuid)
        if sub is None or sub.user_id != user.id:
            raise NotFoundException("Subscription not found.")
        if sub.status in ("cancelled", "completed", "expired") or not sub.provider_subscription_id:
            raise BadRequestException("This plan is not renewing.")
        # Before the first payment there is nothing to keep: cancel at once. Otherwise keep the
        # paid period and stop renewal.
        at_cycle_end = sub.status not in ("created", "authenticated")
        try:
            entity = await self.client.cancel_subscription(sub.provider_subscription_id, at_cycle_end=at_cycle_end)
        except RazorpayError as exc:
            raise ServiceUnavailableException("Couldn't cancel right now. Please try again.") from exc
        self._apply_entity(sub, entity)
        sub.cancel_at_period_end = at_cycle_end
        if not at_cycle_end:
            sub.status = "cancelled"
        sub.cancelled_at = sub.cancelled_at or datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    # ------------------------------------------------------------------------------ status

    async def overview(self, user_id: UUID) -> Dict[str, Any]:
        ent = await get_entitlements(self.db, user_id)
        subs = (await self.db.execute(
            select(Subscription, SubscriptionPlan)
            .join(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
            .where(Subscription.user_id == user_id, Subscription.status != "created")
            .order_by(Subscription.started_at.desc())
            .limit(10)
        )).all()
        now = datetime.now(timezone.utc)
        return {
            "entitlements": ent.as_dict(),
            "usage": {
                "likes_today": await likes_today(self.db, user_id),
                "likes_reset_at": next_reset_utc(),
                "active_listings": await active_listing_count(self.db, user_id),
                "featured_listings": await featured_listing_count(self.db, user_id),
            },
            "subscriptions": [
                {
                    "id": s.id, "plan_code": p.code, "plan_name": p.name, "status": s.status,
                    "expires_at": s.expires_at, "cancel_at_period_end": s.cancel_at_period_end,
                    "is_live": bool(s.expires_at and s.expires_at > now),
                    "renews": s.status in ("authenticated", "active", "pending") and not s.cancel_at_period_end,
                    "price_inr": p.price_inr,
                }
                for s, p in subs
            ],
        }

    # ------------------------------------------------------------------------------ webhooks

    def _apply_entity(self, sub: Subscription, entity: Dict[str, Any]) -> None:
        status = entity.get("status")
        if isinstance(status, str) and status:
            sub.status = status
        start, end = _ts(entity.get("current_start")), _ts(entity.get("current_end"))
        if start:
            sub.current_start = start
        if end:
            sub.expires_at = end
        if entity.get("short_url"):
            sub.short_url = entity["short_url"]
        if status == "cancelled":
            sub.cancelled_at = sub.cancelled_at or _ts(entity.get("ended_at")) or datetime.now(timezone.utc)

    async def handle_webhook(self, raw_body: bytes, signature: Optional[str], event_id: Optional[str]) -> str:
        """Returns "processed", "duplicate" or "ignored". Raises on a bad signature."""
        if not verify_webhook_signature(raw_body, signature):
            raise UnauthorizedException("Invalid webhook signature.", error_code="INVALID_SIGNATURE")
        import json

        try:
            event = json.loads(raw_body)
        except ValueError as exc:
            raise BadRequestException("Malformed webhook body.") from exc
        event_type = str(event.get("event") or "")
        # Razorpay sends the event id in a header; fall back to a stable id from the payload.
        event_id = (event_id or "").strip() or f"{event_type}:{event.get('created_at')}:{json.dumps(event.get('payload'), sort_keys=True)[:200]}"

        # Store the delivery first, in its own transaction, so a processing failure is recorded
        # and Razorpay's retry can process it again. Finished events are never re-applied.
        await self.db.execute(
            pg_insert(BillingEvent)
            .values(provider="razorpay", event_id=event_id[:100], event_type=event_type[:64],
                    payload=event, status="received")
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        await self.db.commit()
        stored = (await self.db.execute(
            select(BillingEvent).where(BillingEvent.event_id == event_id[:100])
        )).scalar_one()
        if stored.status in ("processed", "ignored"):
            return "duplicate"

        try:
            outcome = await self._on_subscription_event(event_type, event)                 if event_type.startswith("subscription.") else "ignored"
            stored.status, stored.error = outcome, None
            stored.processed_at = datetime.now(timezone.utc)
            await self.db.commit()
        except Exception as exc:  # recorded, then surfaced: Razorpay retries non-2xx deliveries
            await self.db.rollback()
            await self.db.execute(
                update(BillingEvent).where(BillingEvent.event_id == event_id[:100])
                .values(status="failed", error=f"{type(exc).__name__}: {exc}"[:500],
                        processed_at=datetime.now(timezone.utc))
            )
            await self.db.commit()
            logger.exception("Billing webhook %s failed", event_type)
            raise
        return outcome

    async def _on_subscription_event(self, event_type: str, event: Dict[str, Any]) -> str:
        payload = event.get("payload") or {}
        entity = (payload.get("subscription") or {}).get("entity") or {}
        provider_id = entity.get("id")
        if not provider_id:
            return "ignored"
        sub = (await self.db.execute(
            select(Subscription).where(Subscription.provider_subscription_id == provider_id).with_for_update()
        )).scalar_one_or_none()
        if sub is None:
            return "ignored"  # not created through this app (e.g. the dashboard)

        created_at = int(event.get("created_at") or 0)
        if sub.provider_event_at and created_at and created_at < sub.provider_event_at:
            # An older event delivered late: record the payment it carries, but don't let it
            # move the subscription backwards.
            await self._record_payment(sub, payload)
            return "processed"

        previous_end = sub.expires_at
        self._apply_entity(sub, entity)
        if created_at:
            sub.provider_event_at = created_at
        if event_type == "subscription.cancelled":
            sub.cancel_at_period_end = False
        await self._record_payment(sub, payload)

        # Renewed: featured listings stay featured for the new period.
        if sub.expires_at and (previous_end is None or sub.expires_at > previous_end):
            plan = await self.db.get(SubscriptionPlan, sub.plan_id)
            if plan and int((plan.features or {}).get("featured_slots") or 0) > 0:
                await self.db.execute(
                    update(Property)
                    .where(Property.owner_id == sub.user_id, Property.featured_until.is_not(None),
                           Property.featured_until > datetime.now(timezone.utc))
                    .values(featured_until=sub.expires_at)
                )

        if event_type in _NOTIFY:
            await self._notify(sub, event_type)
        return "processed"

    async def _record_payment(self, sub: Subscription, payload: Dict[str, Any]) -> None:
        payment = (payload.get("payment") or {}).get("entity") or {}
        pay_id = payment.get("id")
        if not pay_id:
            return
        status = {"captured": "successful", "authorized": "pending", "failed": "failed",
                  "refunded": "refunded"}.get(str(payment.get("status") or ""), "pending")
        values = dict(
            user_id=sub.user_id, subscription_id=sub.id,
            amount=Decimal(int(payment.get("amount") or 0)) / 100,
            currency=(payment.get("currency") or "INR")[:3], status=status, provider="razorpay",
            method=(payment.get("method") or None), gateway_payment_id=pay_id,
            gateway_order_id=payment.get("order_id"), gateway_invoice_id=payment.get("invoice_id"),
            failure_reason=(payment.get("error_description") or None),
            paid_at=_ts(payment.get("created_at")) if status == "successful" else None,
        )
        await self.db.execute(
            pg_insert(Payment).values(**values)
            .on_conflict_do_update(index_elements=["gateway_payment_id"],
                                   set_={"status": status, "failure_reason": values["failure_reason"],
                                         "paid_at": values["paid_at"]})
        )

    async def _notify(self, sub: Subscription, event_type: str) -> None:
        from app.modules.notifications.service import NotificationService

        plan = await self.db.get(SubscriptionPlan, sub.plan_id)
        title, body = _NOTIFY[event_type]
        try:
            await NotificationService(self.db).create_notification(
                user_id=sub.user_id, title=title, body=body.format(plan=plan.name if plan else "your plan"),
                notification_type="billing", reference_id=sub.id, link="/pricing",
            )
        except Exception:  # a notification must never fail a payment event
            logger.warning("Billing notification failed for %s", sub.id, exc_info=True)


async def feature_listing(db: AsyncSession, owner_id: UUID, property_id: UUID, on: bool) -> Property:
    from app.core.exceptions import ForbiddenException, PaymentRequiredException

    prop = await db.get(Property, property_id)
    if prop is None:
        raise NotFoundException("Property not found")
    if prop.owner_id != owner_id:
        raise ForbiddenException("Only the owner can feature this listing")
    if not on:
        prop.featured_until = None
        await db.commit()
        return prop
    if prop.listing_status != "published" or not prop.is_active:
        raise BadRequestException("Only published listings can be featured.")
    ent = await get_entitlements(db, owner_id)
    if ent.featured_slots <= 0 or ent.paid_until is None:
        raise PaymentRequiredException(
            "Featuring listings is part of Owner Pro.", feature="featured_listings", plan="owner_pro")
    if await featured_listing_count(db, owner_id, exclude_id=prop.id) >= ent.featured_slots:
        raise PaymentRequiredException(
            f"You can feature {ent.featured_slots} listings at a time. Unfeature one first.",
            feature="featured_listings", plan="owner_pro", error_code="FEATURED_LIMIT")
    prop.featured_until = ent.paid_until
    await db.commit()
    return prop


__all__ = ["BillingService", "CheckoutSession", "feature_listing", "live_subscription_filter"]
