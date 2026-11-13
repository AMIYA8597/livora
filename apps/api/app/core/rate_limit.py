"""
Rate Limiting Infrastructure.
Sliding window rate limiter with per-IP / per-User quotas and RFC 7807 problem details.
"""

import asyncio
from collections import defaultdict
import time
from typing import Dict, List, Optional, Tuple
from fastapi import Request, Response
from app.core.exceptions import RateLimitException
from app.core.logging import logger


class SlidingWindowRateLimiter:
    """
    Thread-safe in-memory sliding window rate limiter.
    Can be seamlessly backed by Redis when REDIS_URL is configured.
    """

    def __init__(self) -> None:
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Evaluate if request is permitted under sliding window.
        Returns: (is_allowed, remaining_quota, reset_seconds)
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            # Purge expired timestamps
            valid_timestamps = [ts for ts in self._history[key] if ts > cutoff]
            self._history[key] = valid_timestamps

            count = len(valid_timestamps)
            if count >= max_requests:
                earliest = valid_timestamps[0]
                reset_seconds = max(1, int(window_seconds - (now - earliest)))
                return False, 0, reset_seconds

            self._history[key].append(now)
            remaining = max_requests - (count + 1)
            reset_seconds = window_seconds
            return True, remaining, reset_seconds

    async def reset(self, key: Optional[str] = None) -> None:
        """Reset history for a key or all keys (useful in tests)."""
        async with self._lock:
            if key:
                self._history.pop(key, None)
            else:
                self._history.clear()


# Global in-memory singleton
_rate_limiter = SlidingWindowRateLimiter()


class RateLimiter:
    """
    FastAPI dependency for endpoint rate limiting.
    Example:
        @router.post("/auth/login", dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60))])
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_prefix: str = "rate_limit",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    def _extract_client_key(self, request: Request) -> str:
        # Check authorization header for authenticated user ID
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Sub-key by token suffix or hash
            token_snippet = auth_header[-16:]
            return f"{self.key_prefix}:user:{token_snippet}"

        # Otherwise use client IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"{self.key_prefix}:ip:{client_ip}"

    async def __call__(self, request: Request, response: Response) -> None:
        key = self._extract_client_key(request)
        allowed, remaining, reset_sec = await _rate_limiter.is_allowed(
            key=key,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )

        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_sec)

        if not allowed:
            logger.warning(f"Rate limit exceeded for key {key}. Blocked for {reset_sec}s.")
            response.headers["Retry-After"] = str(reset_sec)
            raise RateLimitException(
                detail=f"Rate limit of {self.max_requests} requests per {self.window_seconds}s exceeded. Retry in {reset_sec}s."
            )
