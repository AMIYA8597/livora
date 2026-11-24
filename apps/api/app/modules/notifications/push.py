"""
Web Push (RFC 8030 with VAPID, RFC 8292) for in-app notifications.

  * Push is on only when VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are set.
  * Browsers hand us an endpoint URL that the server later POSTs to. To stop that being used to
    make the server call arbitrary hosts (SSRF), only the real browser push services are
    accepted, over HTTPS on the default port.
  * Delivery runs in the outbox worker (`push.send`), never in the request. Payloads are
    encrypted end to end by pywebpush. Message pushes never carry message text.
  * A subscription the push service reports gone (404/410) is deleted; one that keeps failing
    is dropped after MAX_FAILURES. Transient failures are not retried: the notification is
    still in the app, and a late push is worse than none.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger("flatmate.push")

PUSH_EVENT = "push.send"
MAX_FAILURES = 10
TIMEOUT_SECONDS = 10.0

# Host suffixes of the browser push services (Chrome/Edge/Opera via FCM, Firefox, Windows, Safari).
PUSH_HOST_SUFFIXES = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
    "push.apple.com",
)

TTL_SECONDS = {"messages": 6 * 3600}
DEFAULT_TTL_SECONDS = 24 * 3600


def push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def _b64url_len(value: str) -> int:
    try:
        return len(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    except (ValueError, TypeError):
        return -1


def validate_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    url = urlparse(endpoint or "")
    host = (url.hostname or "").lower()
    if (
        url.scheme != "https"
        or url.port not in (None, 443)
        or url.username or url.password
        or not any(host == s or host.endswith("." + s) for s in PUSH_HOST_SUFFIXES)
    ):
        raise BadRequestException("This browser's push service isn't supported")
    if _b64url_len(p256dh) != 65 or _b64url_len(auth) != 16:
        raise BadRequestException("Invalid push subscription keys")


class PushGone(Exception):
    """The push service says this subscription no longer exists."""


def _send_sync(subscription: Dict[str, Any], data: str, ttl: int, urgency: str) -> None:
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription,
            data=data,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=ttl,
            timeout=TIMEOUT_SECONDS,
            headers={"Urgency": urgency},
        )
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            raise PushGone() from exc
        raise


# Indirection so tests can capture deliveries without a push service.
Sender = Callable[[Dict[str, Any], str, int, str], None]
_sender: Sender = _send_sync


def set_sender(sender: Optional[Sender]) -> None:
    global _sender
    _sender = sender or _send_sync


def build_payload(notification: Dict[str, Any]) -> str:
    return json.dumps({
        "id": notification["id"],
        "title": (notification.get("title") or "Flatmate")[:120],
        "body": (notification.get("body") or "")[:200],
        "url": notification.get("link") or "/notifications",
        "tag": notification["id"],
        "category": notification.get("category"),
    })


async def handle_push(payload: Dict[str, Any], session_factory: async_sessionmaker[AsyncSession]) -> Dict[str, Any]:
    """Outbox handler: deliver one notification to every browser the user subscribed."""
    from app.modules.notifications.models import PushSubscription

    if not push_enabled():
        return {"skipped": "push disabled"}
    async with session_factory() as session:
        subs = (await session.execute(
            select(PushSubscription).where(PushSubscription.user_id == payload["user_id"])
        )).scalars().all()
        targets = [(s.id, {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}) for s in subs]

    category = payload.get("category") or "account"
    ttl = TTL_SECONDS.get(category, DEFAULT_TTL_SECONDS)
    urgency = "high" if category == "messages" else "normal"
    data = build_payload(payload)
    sent, gone, failed = [], [], []
    for sub_id, info in targets:
        try:
            await asyncio.to_thread(_sender, info, data, ttl, urgency)
            sent.append(sub_id)
        except PushGone:
            gone.append(sub_id)
        except Exception as exc:  # noqa: BLE001 - network or push-service error
            logger.warning("Push delivery failed: %s", type(exc).__name__)
            failed.append(sub_id)

    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        if gone:
            await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(gone)))
        for sub in (await session.execute(
            select(PushSubscription).where(PushSubscription.id.in_(sent + failed))
        )).scalars().all():
            if sub.id in sent:
                sub.failure_count, sub.last_success_at = 0, now
            else:
                sub.failure_count += 1
                if sub.failure_count >= MAX_FAILURES:
                    await session.delete(sub)
        await session.commit()
    # The outbox scrubs payloads after success; keep only counts.
    return {"sent": len(sent), "gone": len(gone), "failed": len(failed), "scrubbed": True}
