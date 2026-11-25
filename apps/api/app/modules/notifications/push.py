"""
Web Push (RFC 8030 with VAPID, RFC 8292) for in-app notifications, and the `push.send`
outbox handler that also delivers to the Android and iOS apps (`native_push.py`).

  * Push is on only when VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY are set.
  * Browsers hand us an endpoint URL that the server later POSTs to. To stop that being used to
    make the server call arbitrary hosts (SSRF), only the real browser push services are
    accepted, over HTTPS on the default port.
  * Delivery runs in the outbox worker (`push.send`), never in the request. Payloads are
    encrypted end to end by pywebpush. Message pushes never carry message text.
  * A subscription the push service reports gone (404/410) is deleted; one that keeps failing
    is dropped after MAX_FAILURES.
  * Temporary failures (timeouts, network errors, 429, 5xx) are retried through the outbox, for
    the failed browsers only (the others already have it). The delay follows the service's
    Retry-After, else backs off from RETRY_BASE_SECONDS. Retries stop after MAX_PUSH_ATTEMPTS,
    after RETRY_WINDOW, or once the notification has been read: the notification is still in
    the app, and a late push is worse than none.
"""
from __future__ import annotations

import asyncio
import functools
import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
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

# Retries of temporary failures (see the module docstring).
MAX_PUSH_ATTEMPTS = 4
RETRY_BASE_SECONDS = 30
MAX_RETRY_AFTER_SECONDS = 600
RETRY_WINDOW = timedelta(minutes=30)

TTL_SECONDS = {"messages": 6 * 3600}
DEFAULT_TTL_SECONDS = 24 * 3600


def web_push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def push_enabled() -> bool:
    """Any push channel: Web Push, or native push for at least one app platform."""
    from app.modules.notifications.native_push import enabled_platforms

    return web_push_enabled() or bool(enabled_platforms())


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


class PushRetryable(Exception):
    """A temporary failure (timeout, network, 429, 5xx); worth trying again later."""

    def __init__(self, retry_after: Optional[float] = None):
        super().__init__("temporary push failure")
        self.retry_after = retry_after


def _retry_after(response: Any) -> Optional[float]:
    """Seconds from a Retry-After header (delta-seconds form; dates are rare and ignored)."""
    try:
        value = float(response.headers.get("Retry-After"))
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _send_sync(subscription: Dict[str, Any], data: str, ttl: int, urgency: str) -> None:
    import requests
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
        if status == 429 or (status is not None and status >= 500):
            raise PushRetryable(_retry_after(exc.response)) from exc
        raise
    except requests.RequestException as exc:  # timeout, connection reset, DNS
        raise PushRetryable() from exc


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


def retry_delay(attempt: int, retry_after: Optional[float]) -> float:
    """Seconds before attempt `attempt + 1`: the service's Retry-After if given, else backoff."""
    backoff = RETRY_BASE_SECONDS * 2 ** max(attempt - 1, 0)
    return min(max(backoff, retry_after or 0), MAX_RETRY_AFTER_SECONDS)


def _first_attempt_at(payload: Dict[str, Any], now: datetime) -> datetime:
    try:
        return datetime.fromisoformat(payload["first_attempt_at"])
    except (KeyError, TypeError, ValueError):
        return now


def native_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """What the apps get: the same fields as the Web Push payload."""
    data = json.loads(build_payload(payload))
    return {"id": data["id"], "title": data["title"], "body": data["body"], "url": data["url"],
            "category": data["category"] or "account"}


async def handle_push(payload: Dict[str, Any], session_factory: async_sessionmaker[AsyncSession]) -> Dict[str, Any]:
    """Outbox handler: deliver one notification to every browser and app the user registered
    (or, on a retry, only to the ones that failed temporarily last time)."""
    from app.modules.messaging.models import OutboxEvent
    from app.modules.notifications import native_push
    from app.modules.notifications.models import DevicePushToken, Notification, PushSubscription

    if not push_enabled():
        return {"skipped": "push disabled"}
    attempt = int(payload.get("attempt") or 1)
    is_retry = "subscription_ids" in payload or "device_ids" in payload
    platforms = native_push.enabled_platforms()
    async with session_factory() as session:
        if attempt > 1:
            is_read = (await session.execute(
                select(Notification.is_read).where(Notification.id == payload["id"])
            )).scalar_one_or_none()
            if is_read is None or is_read:
                return {"skipped": "already read or removed", "attempt": attempt, "scrubbed": True}
        web: List[Tuple[Any, Dict[str, Any]]] = []
        if web_push_enabled():
            query = select(PushSubscription).where(PushSubscription.user_id == payload["user_id"])
            if is_retry:
                query = query.where(PushSubscription.id.in_(payload.get("subscription_ids") or []))
            web = [(s.id, {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}})
                   for s in (await session.execute(query)).scalars().all()]
        devices: List[Tuple[Any, str, str]] = []
        if platforms:
            query = select(DevicePushToken).where(
                DevicePushToken.user_id == payload["user_id"], DevicePushToken.platform.in_(platforms)
            )
            if is_retry:
                query = query.where(DevicePushToken.id.in_(payload.get("device_ids") or []))
            devices = [(d.id, d.platform, d.token) for d in (await session.execute(query)).scalars().all()]

    category = payload.get("category") or "account"
    ttl = TTL_SECONDS.get(category, DEFAULT_TTL_SECONDS)
    urgency = "high" if category == "messages" else "normal"
    data = build_payload(payload)
    message = native_message(payload)
    # Results per kind ("web" subscriptions, "device" tokens).
    sent: Dict[str, list] = {"web": [], "device": []}
    gone: Dict[str, list] = {"web": [], "device": []}
    failed: Dict[str, list] = {"web": [], "device": []}
    temporary: List[Tuple[str, Any, Optional[float]]] = []

    async def deliver(kind: str, target_id: Any, call: Callable[[], None]) -> None:
        try:
            await asyncio.to_thread(call)
            sent[kind].append(target_id)
        except PushGone:
            gone[kind].append(target_id)
        except PushRetryable as exc:
            temporary.append((kind, target_id, exc.retry_after))
        except Exception as exc:  # noqa: BLE001 - a permanent push-service error
            logger.warning("Push delivery failed: %s", type(exc).__name__)
            failed[kind].append(target_id)

    for sub_id, info in web:
        await deliver("web", sub_id, functools.partial(_sender, info, data, ttl, urgency))
    for device_id, platform, token in devices:
        await deliver("device", device_id, functools.partial(native_push.send, platform, token, message, ttl, urgency))

    now = datetime.now(timezone.utc)
    first_at = _first_attempt_at(payload, now)
    retry: Optional[OutboxEvent] = None
    if temporary:
        delay = retry_delay(attempt, max((ra or 0 for _, _, ra in temporary), default=0))
        next_at = now + timedelta(seconds=delay)
        if attempt < MAX_PUSH_ATTEMPTS and next_at - first_at <= RETRY_WINDOW:
            retry = OutboxEvent(event_type=PUSH_EVENT, status="pending", next_attempt_at=next_at, payload={
                **{k: v for k, v in payload.items()
                   if k not in ("subscription_ids", "device_ids", "attempt", "first_attempt_at")},
                "subscription_ids": [str(i) for kind, i, _ in temporary if kind == "web"],
                "device_ids": [str(i) for kind, i, _ in temporary if kind == "device"],
                "attempt": attempt + 1,
                "first_attempt_at": first_at.isoformat(),
            })
        else:
            logger.warning("Push gave up after %s attempts", attempt)
            for kind, target_id, _ in temporary:
                failed[kind].append(target_id)

    async with session_factory() as session:
        if retry is not None:
            session.add(retry)
        for kind, model in (("web", PushSubscription), ("device", DevicePushToken)):
            if gone[kind]:
                await session.execute(delete(model).where(model.id.in_(gone[kind])))
            touched = sent[kind] + failed[kind]
            if not touched:
                continue
            for row in (await session.execute(select(model).where(model.id.in_(touched)))).scalars().all():
                if row.id in sent[kind]:
                    row.failure_count, row.last_success_at = 0, now
                else:
                    row.failure_count += 1
                    if row.failure_count >= MAX_FAILURES:
                        await session.delete(row)
        await session.commit()
    # The outbox scrubs payloads after success; keep only counts.
    return {
        "sent": len(sent["web"]) + len(sent["device"]),
        "gone": len(gone["web"]) + len(gone["device"]),
        "failed": len(failed["web"]) + len(failed["device"]),
        "retrying": len(temporary) if retry is not None else 0,
        "attempt": attempt,
        "scrubbed": True,
    }
