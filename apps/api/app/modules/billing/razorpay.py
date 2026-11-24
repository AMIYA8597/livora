"""
Razorpay REST client (subscriptions) and signature checks.

Only what billing needs: plans, subscriptions, cancellation. Amounts are in paise. Errors become
`RazorpayError`; the caller decides what the user sees. Secrets never appear in logs or errors.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("flatmate.billing.razorpay")

API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def billing_enabled() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET and settings.RAZORPAY_WEBHOOK_SECRET)


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature: Optional[str], secret: Optional[str] = None) -> bool:
    """X-Razorpay-Signature = hex HMAC-SHA256 of the raw request body with the webhook secret."""
    secret = secret if secret is not None else settings.RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), signature.strip())


def verify_subscription_payment_signature(
    payment_id: str, subscription_id: str, signature: str, secret: Optional[str] = None
) -> bool:
    """Checkout handler signature for subscriptions: HMAC-SHA256 of
    "<razorpay_payment_id>|<razorpay_subscription_id>" with the API key secret."""
    secret = secret if secret is not None else settings.RAZORPAY_KEY_SECRET
    if not secret or not payment_id or not subscription_id or not signature:
        return False
    expected = _hmac_hex(secret, f"{payment_id}|{subscription_id}".encode("utf-8"))
    return hmac.compare_digest(expected, signature.strip())


class RazorpayClient:
    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: Optional[float] = None,
    ):
        self._auth = (key_id or settings.RAZORPAY_KEY_ID or "", key_secret or settings.RAZORPAY_KEY_SECRET or "")
        self._transport = transport
        self._timeout = timeout or settings.RAZORPAY_TIMEOUT_SECONDS

    async def _request(self, method: str, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not all(self._auth):
            raise RazorpayError("Razorpay is not configured")
        try:
            async with httpx.AsyncClient(
                base_url=API_BASE, auth=self._auth, timeout=self._timeout, transport=self._transport
            ) as client:
                res = await client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning("Razorpay %s %s failed: %s", method, path, type(exc).__name__)
            raise RazorpayError("Couldn't reach the payment provider") from exc
        if res.status_code >= 400:
            try:
                description = res.json().get("error", {}).get("description") or ""
            except ValueError:
                description = ""
            logger.warning("Razorpay %s %s -> %s %s", method, path, res.status_code, description[:200])
            raise RazorpayError(description or "The payment provider rejected the request", res.status_code)
        try:
            return res.json()
        except ValueError as exc:
            raise RazorpayError("Unexpected response from the payment provider") from exc

    async def create_plan(self, *, name: str, amount_paise: int, period: str, interval: int,
                          description: str = "", notes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self._request("POST", "/plans", {
            "period": period,
            "interval": interval,
            "item": {"name": name, "amount": amount_paise, "currency": "INR", "description": description[:250]},
            "notes": notes or {},
        })

    async def create_subscription(self, *, plan_id: str, total_count: int,
                                  notes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        return await self._request("POST", "/subscriptions", {
            "plan_id": plan_id,
            "total_count": total_count,
            "quantity": 1,
            "customer_notify": 1,
            "notes": notes or {},
        })

    async def fetch_subscription(self, subscription_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/subscriptions/{subscription_id}")

    async def cancel_subscription(self, subscription_id: str, *, at_cycle_end: bool) -> Dict[str, Any]:
        return await self._request(
            "POST", f"/subscriptions/{subscription_id}/cancel",
            {"cancel_at_cycle_end": 1 if at_cycle_end else 0},
        )
