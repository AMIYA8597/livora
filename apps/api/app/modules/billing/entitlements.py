"""
What a user may do, from their plans.

- Free tier (billing on): `FREE_DAILY_LIKES` likes a day, `FREE_ACTIVE_LISTINGS` published
  listings, no "who liked you", no featured listings.
- Billing off (no Razorpay keys): no limits at all, and the paid-only features don't exist. The
  product behaves as it did before payments, so nothing is locked behind a checkout that can't
  run.
- A plan's `features` override the free values; `null` means unlimited. A user with several
  plans gets the most generous value of each.

A subscription grants access while its paid period lasts (`expires_at` in the future), whatever
its status: a cancelled plan stays usable for the time already paid for.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PaymentRequiredException
from app.modules.billing.razorpay import billing_enabled
from app.modules.subscriptions.models import Subscription, SubscriptionPlan

IST = ZoneInfo("Asia/Kolkata")
UNLIMITED = None


@dataclass
class Entitlements:
    billing_enabled: bool
    who_liked_me: bool
    daily_likes: Optional[int]  # None = unlimited
    max_active_listings: Optional[int]  # None = unlimited
    featured_slots: int
    plans: List[str] = field(default_factory=list)
    # When the most generous paid access ends (for featured listings).
    paid_until: Optional[datetime] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _more(a: Optional[int], b: Any) -> Optional[int]:
    """The more generous of two limits (None = unlimited wins)."""
    if a is UNLIMITED or b is None:
        return UNLIMITED
    try:
        return max(a, int(b))
    except (TypeError, ValueError):
        return a


def free_entitlements() -> Entitlements:
    if not billing_enabled():
        return Entitlements(billing_enabled=False, who_liked_me=False, daily_likes=UNLIMITED,
                            max_active_listings=UNLIMITED, featured_slots=0)
    return Entitlements(billing_enabled=True, who_liked_me=False, daily_likes=settings.FREE_DAILY_LIKES,
                        max_active_listings=settings.FREE_ACTIVE_LISTINGS, featured_slots=0)


def live_subscription_filter(now: Optional[datetime] = None):
    now = now or datetime.now(timezone.utc)
    return and_(Subscription.expires_at.is_not(None), Subscription.expires_at > now,
                Subscription.status != "created")


async def get_entitlements(db: AsyncSession, user_id: UUID) -> Entitlements:
    ent = free_entitlements()
    if not ent.billing_enabled:
        return ent
    rows = (await db.execute(
        select(SubscriptionPlan.code, SubscriptionPlan.features, Subscription.expires_at)
        .join(Subscription, Subscription.plan_id == SubscriptionPlan.id)
        .where(Subscription.user_id == user_id, live_subscription_filter())
    )).all()
    for code, features, expires_at in rows:
        f = features or {}
        ent.plans.append(code)
        ent.who_liked_me = ent.who_liked_me or bool(f.get("who_liked_me"))
        if "daily_likes" in f:
            ent.daily_likes = _more(ent.daily_likes, f["daily_likes"])
        if "max_active_listings" in f:
            ent.max_active_listings = _more(ent.max_active_listings, f["max_active_listings"])
        try:
            ent.featured_slots = max(ent.featured_slots, int(f.get("featured_slots") or 0))
        except (TypeError, ValueError):
            pass
        if ent.paid_until is None or expires_at > ent.paid_until:
            ent.paid_until = expires_at
    return ent


def start_of_today_utc(now: Optional[datetime] = None) -> datetime:
    """Midnight in India, as UTC: daily limits reset at local midnight."""
    local = (now or datetime.now(timezone.utc)).astimezone(IST)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def next_reset_utc(now: Optional[datetime] = None) -> datetime:
    return start_of_today_utc(now) + timedelta(days=1)


async def likes_today(db: AsyncSession, user_id: UUID) -> int:
    from app.modules.matching.models import MatchInteraction

    return int(await db.scalar(
        select(func.count()).select_from(MatchInteraction).where(
            MatchInteraction.user_id == user_id,
            MatchInteraction.action.in_(("like", "super_like")),
            MatchInteraction.created_at >= start_of_today_utc(),
        )
    ) or 0)


async def active_listing_count(db: AsyncSession, owner_id: UUID, exclude_id: Optional[UUID] = None) -> int:
    from app.modules.properties.models import Property

    conditions = [Property.owner_id == owner_id, Property.is_active.is_(True), Property.listing_status == "published"]
    if exclude_id is not None:
        conditions.append(Property.id != exclude_id)
    return int(await db.scalar(select(func.count()).select_from(Property).where(*conditions)) or 0)


async def featured_listing_count(db: AsyncSession, owner_id: UUID, exclude_id: Optional[UUID] = None) -> int:
    from app.modules.properties.models import Property

    conditions = [Property.owner_id == owner_id, Property.featured_until > datetime.now(timezone.utc)]
    if exclude_id is not None:
        conditions.append(Property.id != exclude_id)
    return int(await db.scalar(select(func.count()).select_from(Property).where(*conditions)) or 0)


# ---------------------------------------------------------------------------------- guards


async def ensure_can_like(db: AsyncSession, user_id: UUID) -> None:
    ent = await get_entitlements(db, user_id)
    if ent.daily_likes is UNLIMITED:
        return
    if await likes_today(db, user_id) >= ent.daily_likes:
        raise PaymentRequiredException(
            f"You've used today's {ent.daily_likes} likes. They reset at midnight, or get Seeker Pro "
            "to like without a limit.",
            feature="unlimited_likes", plan="seeker_pro",
        )


async def ensure_can_publish(db: AsyncSession, owner_id: UUID, property_id: Optional[UUID] = None) -> None:
    ent = await get_entitlements(db, owner_id)
    if ent.max_active_listings is UNLIMITED:
        return
    if await active_listing_count(db, owner_id, exclude_id=property_id) >= ent.max_active_listings:
        raise PaymentRequiredException(
            f"Free accounts can have {ent.max_active_listings} published listings at a time. Pause one, "
            "or get Owner Pro to publish more.",
            feature="unlimited_listings", plan="owner_pro",
        )
