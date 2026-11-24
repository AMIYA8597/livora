"""Billing API: plans, checkout, verification, cancellation, status and the Razorpay webhook."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter
from app.modules.billing.razorpay import billing_enabled
from app.modules.billing.service import BillingService
from app.modules.users.models import User

router = APIRouter(prefix="/billing", tags=["Billing"])


class PlanOut(BaseModel):
    code: str
    name: str
    audience: str
    description: Optional[str] = None
    price_inr: Decimal
    period: str
    interval: int
    features: Dict[str, Any]


class PlansOut(BaseModel):
    enabled: bool
    plans: List[PlanOut]


class CheckoutIn(BaseModel):
    plan_code: str = Field(..., max_length=50)


class CheckoutOut(BaseModel):
    subscription_id: str
    key_id: str
    plan_code: str
    plan_name: str
    amount_inr: Decimal
    prefill: Dict[str, str]


class VerifyIn(BaseModel):
    razorpay_payment_id: str = Field(..., max_length=64)
    razorpay_subscription_id: str = Field(..., max_length=64)
    razorpay_signature: str = Field(..., max_length=128)


class SubscriptionOut(BaseModel):
    id: UUID
    status: str
    expires_at: Optional[datetime] = None
    cancel_at_period_end: bool


@router.get("/plans", response_model=PlansOut)
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Public: the plan catalogue, and whether checkout is available."""
    plans = await BillingService(db).list_plans()
    return PlansOut(enabled=billing_enabled(), plans=[
        PlanOut(code=p.code, name=p.name, audience=p.audience, description=p.description,
                price_inr=p.price_inr, period=p.period, interval=p.interval, features=p.features or {})
        for p in plans
    ])


@router.get("/me")
async def my_billing(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Entitlements, today's usage and the user's subscriptions."""
    return await BillingService(db).overview(current_user.id)


@router.post(
    "/subscriptions", response_model=CheckoutOut,
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60, key_prefix="billing_checkout"))],
)
async def start_checkout(
    body: CheckoutIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    s = await BillingService(db).start_checkout(current_user, body.plan_code)
    return CheckoutOut(**s.__dict__)


@router.post(
    "/subscriptions/verify", response_model=SubscriptionOut,
    dependencies=[Depends(RateLimiter(max_requests=20, window_seconds=60, key_prefix="billing_verify"))],
)
async def verify_checkout(
    body: VerifyIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    sub = await BillingService(db).verify(
        current_user, body.razorpay_payment_id, body.razorpay_subscription_id, body.razorpay_signature
    )
    return SubscriptionOut(id=sub.id, status=sub.status, expires_at=sub.expires_at,
                           cancel_at_period_end=sub.cancel_at_period_end)


@router.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    subscription_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    sub = await BillingService(db).cancel(current_user, subscription_id)
    return SubscriptionOut(id=sub.id, status=sub.status, expires_at=sub.expires_at,
                           cancel_at_period_end=sub.cancel_at_period_end)


@router.post("/webhooks/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Signed by Razorpay (X-Razorpay-Signature over the raw body). No user auth."""
    raw = await request.body()
    outcome = await BillingService(db).handle_webhook(
        raw, request.headers.get("x-razorpay-signature"), request.headers.get("x-razorpay-event-id"),
    )
    return {"status": outcome}


__all__ = ["router"]
