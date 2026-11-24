"""
Native push for the Android and iOS apps, next to Web Push (`push.py`).

  * Android: Firebase Cloud Messaging HTTP v1. The server signs a JWT with the service
    account's key, trades it at Google's token endpoint for an access token (cached for its
    hour), and POSTs one message per device.
  * iOS: APNs directly, over HTTP/2 with a token-based (.p8) key. The provider JWT is cached
    and renewed every 50 minutes (Apple rejects tokens older than an hour and throttles
    renewals more often than every 20 minutes).
  * Each platform is on only when all its settings are set (see `config.py`).
  * Messages carry the notification's title and body (already free of message text, see
    `NotificationService`) and a same-site path the app opens on tap. Android notifications
    use a channel per category (messages, matches, rentals, account), which the app creates.
  * Errors are classified like Web Push: `PushGone` (the token is dead: delete it),
    `PushRetryable` (temporary: retry through the outbox), anything else is a permanent
    failure that counts towards dropping the token.

No Firebase or Apple SDK: two small HTTPS calls, signed with python-jose, sent with httpx.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, Optional

from app.core.config import settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger("flatmate.push")

PLATFORMS = ("android", "ios")
TIMEOUT_SECONDS = 10.0

# Google's token endpoint is fixed, not read from the key file, so a tampered key file can't
# send the signed assertion elsewhere.
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
APNS_HOST = "https://api.push.apple.com"
APNS_SANDBOX_HOST = "https://api.sandbox.push.apple.com"
APNS_TOKEN_TTL_SECONDS = 50 * 60

# FCM registration tokens are URL-safe base64 with ':' separators; APNs device tokens are hex
# (32 bytes today; Apple says not to rely on the length, so up to 100 bytes is accepted).
_FCM_TOKEN = re.compile(r"^[A-Za-z0-9_\-:]{32,4096}$")
_APNS_TOKEN = re.compile(r"^[0-9a-fA-F]{64,200}$")

# APNs reasons that mean the token itself is unusable.
APNS_GONE_REASONS = {"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"}
# FCM error codes that mean the token is unusable for this project.
FCM_GONE_CODES = {"UNREGISTERED", "SENDER_ID_MISMATCH"}


def fcm_enabled() -> bool:
    return bool(settings.FCM_PROJECT_ID and settings.FCM_SERVICE_ACCOUNT_JSON)


def apns_enabled() -> bool:
    return bool(settings.APNS_KEY_ID and settings.APNS_TEAM_ID and settings.APNS_BUNDLE_ID and settings.APNS_PRIVATE_KEY)


def platform_enabled(platform: str) -> bool:
    return fcm_enabled() if platform == "android" else apns_enabled() if platform == "ios" else False


def enabled_platforms() -> list[str]:
    return [p for p in PLATFORMS if platform_enabled(p)]


def normalize_token(platform: str, token: str) -> str:
    """The stored form of a device token, or BadRequest if it can't be one."""
    token = (token or "").strip()
    if platform == "ios" and _APNS_TOKEN.match(token):
        return token.lower()
    if platform == "android" and _FCM_TOKEN.match(token):
        return token
    raise BadRequestException("Invalid push token for this platform")


# ---------------------------------------------------------------------------- errors

def _errors():
    from app.modules.notifications.push import PushGone, PushRetryable

    return PushGone, PushRetryable


def _retry_after(response: Any) -> Optional[float]:
    try:
        value = float(response.headers.get("Retry-After"))
    except (AttributeError, TypeError, ValueError):
        return None
    return value if value >= 0 else None


# ---------------------------------------------------------------------------- credentials

_lock = threading.Lock()
_google_token: Dict[str, Any] = {"value": None, "expires": 0.0}
_apns_token: Dict[str, Any] = {"value": None, "issued": 0.0}
_apns_client: Dict[str, Any] = {"client": None}


def reset_credentials() -> None:
    """Forget cached access tokens (after a 401/403, and in tests)."""
    with _lock:
        _google_token.update(value=None, expires=0.0)
        _apns_token.update(value=None, issued=0.0)


def _google_access_token() -> str:
    import httpx
    from jose import jwt

    with _lock:
        if _google_token["value"] and _google_token["expires"] - 60 > time.time():
            return _google_token["value"]
    info = json.loads(settings.FCM_SERVICE_ACCOUNT_JSON or "{}")
    now = int(time.time())
    assertion = jwt.encode(
        {"iss": info["client_email"], "scope": FCM_SCOPE, "aud": GOOGLE_TOKEN_URL, "iat": now, "exp": now + 3600},
        info["private_key"],
        algorithm="RS256",
        headers={"kid": info.get("private_key_id")} if info.get("private_key_id") else None,
    )
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        _, PushRetryable = _errors()
        if response.status_code == 429 or response.status_code >= 500:
            raise PushRetryable(_retry_after(response))
        raise RuntimeError(f"Google token request refused ({response.status_code})")
    body = response.json()
    with _lock:
        _google_token.update(value=body["access_token"], expires=now + int(body.get("expires_in", 3600)))
        return body["access_token"]


def _apns_provider_token() -> str:
    from jose import jwt

    with _lock:
        if _apns_token["value"] and time.time() - _apns_token["issued"] < APNS_TOKEN_TTL_SECONDS:
            return _apns_token["value"]
        now = int(time.time())
        value = jwt.encode(
            {"iss": settings.APNS_TEAM_ID, "iat": now},
            (settings.APNS_PRIVATE_KEY or "").replace("\\n", "\n"),
            algorithm="ES256",
            headers={"kid": settings.APNS_KEY_ID},
        )
        _apns_token.update(value=value, issued=now)
        return value


def _apns_http():
    """One HTTP/2 connection reused for every APNs request (Apple asks for that)."""
    import httpx

    with _lock:
        if _apns_client["client"] is None:
            _apns_client["client"] = httpx.Client(http2=True, timeout=TIMEOUT_SECONDS)
        return _apns_client["client"]


# ---------------------------------------------------------------------------- messages

def fcm_message(token: str, message: Dict[str, Any], ttl: int, urgency: str) -> Dict[str, Any]:
    category = message.get("category") or "account"
    return {"message": {
        "token": token,
        "notification": {"title": message["title"], "body": message["body"]},
        # FCM data values must be strings.
        "data": {"url": message["url"], "id": message["id"], "category": category},
        "android": {
            "priority": "HIGH" if urgency == "high" else "NORMAL",
            "ttl": f"{int(ttl)}s",
            "collapse_key": message["id"],
            "notification": {"tag": message["id"], "channel_id": category},
        },
    }}


def apns_request(token: str, message: Dict[str, Any], ttl: int, urgency: str) -> Dict[str, Any]:
    category = message.get("category") or "account"
    host = APNS_SANDBOX_HOST if settings.APNS_SANDBOX else APNS_HOST
    return {
        "url": f"{host}/3/device/{token}",
        "headers": {
            "apns-topic": settings.APNS_BUNDLE_ID or "",
            "apns-push-type": "alert",
            "apns-priority": "10" if urgency == "high" else "5",
            "apns-expiration": str(int(time.time()) + int(ttl)),
            "apns-collapse-id": message["id"][:64],  # a re-delivered push replaces, never duplicates
        },
        "json": {
            "aps": {"alert": {"title": message["title"], "body": message["body"]}, "sound": "default", "thread-id": category},
            "url": message["url"], "id": message["id"], "category": category,
        },
    }


def _send_fcm(token: str, message: Dict[str, Any], ttl: int, urgency: str) -> None:
    import httpx

    PushGone, PushRetryable = _errors()
    try:
        access = _google_access_token()
        response = httpx.post(
            f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send",
            json=fcm_message(token, message, ttl, urgency),
            headers={"Authorization": f"Bearer {access}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise PushRetryable() from exc
    if response.status_code == 200:
        return
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    codes = {error.get("status")} | {d.get("errorCode") for d in error.get("details", []) if isinstance(d, dict)}
    if response.status_code == 404 or codes & FCM_GONE_CODES:
        raise PushGone()
    if response.status_code == 401:
        reset_credentials()
        raise PushRetryable()
    if response.status_code == 429 or response.status_code >= 500:
        raise PushRetryable(_retry_after(response))
    raise RuntimeError(f"FCM refused the message ({response.status_code} {error.get('status')})")


def _send_apns(token: str, message: Dict[str, Any], ttl: int, urgency: str) -> None:
    import httpx

    PushGone, PushRetryable = _errors()
    request = apns_request(token, message, ttl, urgency)
    try:
        response = _apns_http().post(
            request["url"], json=request["json"],
            headers={**request["headers"], "authorization": f"bearer {_apns_provider_token()}"},
        )
    except httpx.HTTPError as exc:
        raise PushRetryable() from exc
    if response.status_code == 200:
        return
    try:
        reason = response.json().get("reason")
    except ValueError:
        reason = None
    if response.status_code == 410 or reason in APNS_GONE_REASONS:
        raise PushGone()
    if reason == "ExpiredProviderToken":
        reset_credentials()
        raise PushRetryable()
    if response.status_code == 429 or response.status_code >= 500:
        raise PushRetryable(_retry_after(response))
    raise RuntimeError(f"APNs refused the message ({response.status_code} {reason})")


def _send_sync(platform: str, token: str, message: Dict[str, Any], ttl: int, urgency: str) -> None:
    if platform == "android":
        _send_fcm(token, message, ttl, urgency)
    elif platform == "ios":
        _send_apns(token, message, ttl, urgency)
    else:
        raise ValueError(f"unknown platform {platform!r}")


# Indirection so tests can capture deliveries without Firebase or Apple.
NativeSender = Callable[[str, str, Dict[str, Any], int, str], None]
_sender: NativeSender = _send_sync


def set_sender(sender: Optional[NativeSender]) -> None:
    global _sender
    _sender = sender or _send_sync


def send(platform: str, token: str, message: Dict[str, Any], ttl: int, urgency: str) -> None:
    _sender(platform, token, message, ttl, urgency)
