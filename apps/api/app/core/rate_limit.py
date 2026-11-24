"""
Rate limiting shared by every API instance.

Counts live in Redis (a sliding-window log per key, updated atomically by a Lua script), so
limits survive restarts and don't multiply with the number of instances. When Redis isn't
reachable the limiter falls back to a per-process window, which still slows abuse down.

Keys:
  * signed-in calls use the verified user id from the access token (a new token doesn't
    reset the count, and a forged one falls through to the IP key)
  * anonymous calls use the client IP, read from `X-Forwarded-For` only as far as the
    `TRUSTED_PROXY_HOPS` proxies in front of the app vouch for it
  * callers can also limit on their own keys with `hit()` (e.g. one email address)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from collections import defaultdict
from typing import Dict, List, Literal, Optional, Tuple

from fastapi import Request, Response

from app.core.config import settings
from app.core.exceptions import RateLimitException

logger = logging.getLogger("flatmate.rate_limit")

KEY_NAMESPACE = "rl"

# KEYS[1] = bucket; ARGV = now_ms, window_ms, limit, member. Returns {allowed, remaining, reset_ms}.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local reset = window
  if oldest[2] then reset = tonumber(oldest[2]) + window - now end
  return {0, 0, reset}
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, window)
return {1, limit - count - 1, window}
"""


class SlidingWindowRateLimiter:
    """Per-process sliding window: the fallback when Redis is unavailable, and in tests."""

    def __init__(self) -> None:
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, max_requests: int = 60, window_seconds: int = 60) -> Tuple[bool, int, int]:
        """Returns (allowed, remaining, seconds until the window frees up)."""
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            valid = [ts for ts in self._history[key] if ts > cutoff]
            if not valid:
                self._history.pop(key, None)  # don't keep empty keys forever
            if len(valid) >= max_requests:
                self._history[key] = valid
                return False, 0, max(1, int(window_seconds - (now - valid[0])))
            valid.append(now)
            self._history[key] = valid
            return True, max_requests - len(valid), window_seconds

    async def reset(self, key: Optional[str] = None) -> None:
        async with self._lock:
            if key:
                self._history.pop(key, None)
            else:
                self._history.clear()


_memory = SlidingWindowRateLimiter()
_redis_warned = False


async def _redis_is_allowed(key: str, max_requests: int, window_seconds: int) -> Optional[Tuple[bool, int, int]]:
    """None when Redis isn't connected or the call fails, so the caller falls back."""
    global _redis_warned
    from app.infrastructure import cache

    client = cache.redis_client
    if client is None:
        return None
    try:
        allowed, remaining, reset_ms = await client.eval(  # type: ignore[misc]
            _SLIDING_WINDOW_LUA, 1, f"{KEY_NAMESPACE}:{key}",
            str(int(time.time() * 1000)), str(window_seconds * 1000), str(max_requests), uuid.uuid4().hex,
        )
        _redis_warned = False
        return bool(int(allowed)), int(remaining), max(1, -(-int(reset_ms) // 1000))
    except Exception as exc:  # noqa: BLE001 - never fail a request because the limiter's store is down
        if not _redis_warned:
            logger.warning("Rate limiter falling back to per-process counts: %s", type(exc).__name__)
            _redis_warned = True
        return None


async def check(key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int, int]:
    """Count one request against `key`. Returns (allowed, remaining, reset_seconds)."""
    if not settings.RATE_LIMIT_ENABLED:
        return True, max_requests, window_seconds
    result = await _redis_is_allowed(key, max_requests, window_seconds)
    if result is None:
        result = await _memory.is_allowed(key, max_requests, window_seconds)
    return result


async def hit(key: str, max_requests: int, window_seconds: int, message: Optional[str] = None) -> None:
    """Count one request against `key` and raise 429 when it's over the limit."""
    allowed, _, reset = await check(key, max_requests, window_seconds)
    if not allowed:
        logger.warning("Rate limit exceeded for %s", key.split(":", 1)[0])
        raise RateLimitException(detail=message or f"Too many requests. Try again in {reset}s.", retry_after=reset)


async def reset(key: Optional[str] = None) -> None:
    """Clear counts (tests). Only the per-process store; Redis keys expire on their own."""
    await _memory.reset(key)


def hashed(value: str) -> str:
    """Stable, non-reversible key part for things like email addresses (keys never hold PII)."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]


def client_ip(request: Request) -> str:
    """
    The caller's IP. Each proxy in front of the app appends the address it received the
    request from to `X-Forwarded-For`, so with N trusted proxies the real client is the Nth
    entry from the right; anything further left was written by the client and can be forged.
    With no trusted proxies the socket peer is used.
    """
    hops = settings.TRUSTED_PROXY_HOPS
    peer = request.client.host if request.client else "unknown"
    if hops <= 0:
        return peer
    entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
    if len(entries) >= hops:
        return entries[-hops][:64]
    return entries[0][:64] if entries else peer


def verified_user_id(request: Request) -> Optional[str]:
    """User id from a valid access token, or None (missing, expired, forged or a refresh token)."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    from app.core.security import decode_token

    try:
        payload = decode_token(auth[7:].strip())
    except Exception:  # noqa: BLE001 - an invalid token just means "anonymous" here
        return None
    if payload.get("type", "access") != "access" or not payload.get("sub"):
        return None
    return str(payload["sub"])


class RateLimiter:
    """
    FastAPI dependency for endpoint rate limiting.

        @router.post("/x", dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60, key_prefix="x"))])

    `scope="auto"` keys on the signed-in user when there is one, else the client IP;
    `scope="ip"` always keys on the IP (for anonymous endpoints like login).
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_prefix: str = "rate_limit",
        scope: Literal["auto", "ip"] = "auto",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.scope = scope

    def _extract_client_key(self, request: Request) -> str:
        if self.scope == "auto":
            user_id = verified_user_id(request)
            if user_id:
                return f"{self.key_prefix}:user:{user_id}"
        return f"{self.key_prefix}:ip:{client_ip(request)}"

    async def __call__(self, request: Request, response: Response) -> None:
        key = self._extract_client_key(request)
        allowed, remaining, reset_sec = await check(key, self.max_requests, self.window_seconds)

        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_sec)

        if not allowed:
            response.headers["Retry-After"] = str(reset_sec)
            logger.warning("Rate limit exceeded for %s (%s)", self.key_prefix, key.split(":")[1])
            raise RateLimitException(
                detail=f"Too many requests. Try again in {reset_sec}s.",
                retry_after=reset_sec,
            )
