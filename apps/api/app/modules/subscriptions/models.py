"""
Subscription plans, subscriptions, payments and payment-provider events.

Billing runs on Razorpay auto-renewing subscriptions (app/modules/billing). Razorpay's signed
webhooks are the source of truth for subscription state; `expires_at` is the end of the paid
period, and access lasts until then whatever the status (a cancelled plan stays usable for the
time already paid for).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Seeker Pro", "Owner Pro"
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    audience: Mapped[str] = mapped_column(String(16), default="seeker", nullable=False, server_default=text("'seeker'"))  # seeker | owner
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    period: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False, server_default=text("'monthly'"))  # Razorpay period
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False, server_default=text("1"))
    duration_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    # Entitlements this plan grants (app/modules/billing/entitlements.py), e.g.
    # {"who_liked_me": true, "daily_likes": null} or {"max_active_listings": null, "featured_slots": 3}.
    # null = unlimited.
    features: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Razorpay plans are immutable: a new one is created when price_inr changes.
    razorpay_plan_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    razorpay_plan_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # paise
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Razorpay statuses: created, authenticated, active, pending, halted, cancelled, completed,
    # paused, expired. Plus "expired" set by maintenance for non-provider rows.
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    provider: Mapped[str] = mapped_column(String(16), default="razorpay", nullable=False, server_default=text("'razorpay'"))
    provider_subscription_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    short_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    current_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # End of the paid period; access lasts until then. Null until the first charge.
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # created_at of the newest provider event applied, so late or replayed events can't roll
    # the state back.
    provider_event_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, server_default=text("now()"))

    user = relationship("User")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, successful, failed, refunded
    provider: Mapped[str] = mapped_column(String(16), default="razorpay", nullable=False, server_default=text("'razorpay'"))
    method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # upi, card, netbanking...
    gateway_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    gateway_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user = relationship("User")


class BillingEvent(Base):
    """Every verified webhook delivery, once (provider event id is unique). Audit trail and
    idempotency for at-least-once delivery."""

    __tablename__ = "billing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(16), default="razorpay", nullable=False, server_default=text("'razorpay'"))
    event_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="received", nullable=False, server_default=text("'received'"))  # processed, ignored, failed
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, server_default=text("now()"))
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
