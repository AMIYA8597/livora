"""
Short-lived caching for hot, public reads (city lists, anonymous listing pages, owner reply
times).

Two layers:
  * this process's memory, bounded (oldest entries go first), so a hot key costs nothing;
  * Redis when it's connected, so a new or scaled-out instance starts warm and every instance
    serves the same answer.

Concurrent misses for one key are coalesced: one request loads, the others wait for it (no
stampede of identical queries when an entry expires under load). A failing cache never fails a
request: the loader runs instead.

Only cache what is the same for every caller. Values must be JSON-serialisable; use
`jsonable_encoder` on ORM output first.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple

logger = logging.getLogger("flatmate.hot_cache")

NAMESPACE = "hc"
MAX_LOCAL_ENTRIES = 2048

_local: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
_inflight: Dict[str, "asyncio.Future[Any]"] = {}
stats = {"hits": 0, "misses": 0, "redis_hits": 0}


def _local_get(key: str) -> Tuple[bool, Any]:
    entry = _local.get(key)
    if entry is None:
        return False, None
    expires, value = entry
    if expires <= time.monotonic():
        _local.pop(key, None)
        return False, None
    _local.move_to_end(key)
    return True, value


def _local_set(key: str, value: Any, ttl: float) -> None:
    _local[key] = (time.monotonic() + ttl, value)
    _local.move_to_end(key)
    while len(_local) > MAX_LOCAL_ENTRIES:
        _local.popitem(last=False)


async def _redis_get(key: str) -> Tuple[bool, Any]:
    from app.infrastructure import cache

    client = cache.redis_client
    if client is None:
        return False, None
    try:
        raw = await client.get(f"{NAMESPACE}:{key}")
    except Exception:  # noqa: BLE001 - a cache outage must not fail the request
        return False, None
    if raw is None:
        return False, None
    try:
        return True, json.loads(raw)
    except ValueError:
        return False, None


async def _redis_set(key: str, value: Any, ttl: float) -> None:
    from app.infrastructure import cache

    client = cache.redis_client
    if client is None:
        return
    try:
        await client.set(f"{NAMESPACE}:{key}", json.dumps(value), ex=max(1, int(ttl)))
    except Exception:  # noqa: BLE001
        pass


async def cached(key: str, ttl_seconds: float, loader: Callable[[], Awaitable[Any]]) -> Any:
    """The cached value for `key`, loading (once, even under concurrency) when missing."""
    found, value = _local_get(key)
    if found:
        stats["hits"] += 1
        return value

    pending = _inflight.get(key)
    if pending is not None:
        stats["hits"] += 1
        # wait() lets our own cancellation through but not the loading request's: if that one
        # was cancelled (its client went away), load it ourselves.
        await asyncio.wait({pending})
        if pending.cancelled():
            return await loader()
        return pending.result()

    future: "asyncio.Future[Any]" = asyncio.get_running_loop().create_future()
    _inflight[key] = future
    try:
        found, value = await _redis_get(key)
        if found:
            stats["redis_hits"] += 1
        else:
            stats["misses"] += 1
            value = await loader()
            await _redis_set(key, value, ttl_seconds)
        _local_set(key, value, ttl_seconds)
        future.set_result(value)
        return value
    except Exception as exc:
        # Waiters get the same error; the next request tries again.
        if not future.done():
            future.set_exception(exc)
            future.exception()  # mark retrieved: no "exception never retrieved" warning
        raise
    except BaseException:
        if not future.done():
            future.cancel()
        raise
    finally:
        _inflight.pop(key, None)


def clear() -> None:
    """Forget this process's entries (tests)."""
    _local.clear()
    stats.update(hits=0, misses=0, redis_hits=0)


def key_for(prefix: str, **params: Optional[Any]) -> str:
    """A stable cache key from parameters (unset ones left out)."""
    parts = [f"{k}={params[k]}" for k in sorted(params) if params[k] is not None]
    return f"{prefix}?{'&'.join(parts)}"
