"""
Live traffic numbers: what the admin console's Traffic tab and GET /metrics show.

Each process keeps
  * a rolling last-minute view (six 10-second slots): requests, status classes, latency
    histogram, overload refusals and timeouts, per route;
  * running totals since start, for Prometheus (`render_prometheus`).

With Redis, every instance publishes its last-minute view every few seconds (`publish_forever`),
and `fleet_snapshot` adds them up, so the console shows the whole service and not just the
instance that answered. Without Redis it shows this instance only, and says so.

Routes are the templates (`/api/v1/properties/{property_id}`), never raw paths, so the number of
series stays bounded and no IDs end up in the numbers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("flatmate.metrics")

# Latency bucket upper bounds, seconds (the last bucket is everything slower).
BUCKETS: Sequence[float] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
SLOT_SECONDS = 10
SLOTS = 6  # one minute
MAX_ROUTES = 300
OTHER_ROUTE = "(other)"
STATUS_CLASSES = ("2xx", "3xx", "4xx", "5xx")

PUBLISH_EVERY_SECONDS = 5
PUBLISH_TTL_SECONDS = 30
FLEET_SET = "flatmate:metrics:instances"
FLEET_KEY = "flatmate:metrics:instance:{id}"

INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
STARTED_AT = time.time()


def _bucket(seconds: float) -> int:
    for i, bound in enumerate(BUCKETS):
        if seconds <= bound:
            return i
    return len(BUCKETS)


def _empty_hist() -> List[int]:
    return [0] * (len(BUCKETS) + 1)


def _status_class(status: int) -> str:
    return f"{max(2, min(5, status // 100))}xx"


class _Window:
    """Counts for one 10-second slot."""

    __slots__ = ("start", "routes", "shed", "timeouts", "unavailable")

    def __init__(self, start: int) -> None:
        self.start = start
        # route -> {"count", "2xx".., "hist"}
        self.routes: Dict[str, Dict[str, Any]] = {}
        self.shed = 0
        self.timeouts = 0
        self.unavailable = 0


LAG_PROBE_SECONDS = 0.5


class Metrics:
    def __init__(self) -> None:
        self.in_flight = 0
        self.peak_in_flight = 0
        # Event-loop delay: how late a timer fires. Async Python serves everything on one loop,
        # so this is the saturation signal: CPU-bound work or a blocking call shows up here first.
        self.loop_lag_ms = 0.0
        self.loop_lag_max_ms = 0.0
        self._slots: List[Optional[_Window]] = [None] * SLOTS
        # Running totals: (method, route, status class) -> count; route -> histogram and sum.
        self.totals: Dict[tuple, int] = {}
        self.duration_hist: Dict[str, List[int]] = {}
        self.duration_sum: Dict[str, float] = {}
        self.shed_total = 0
        self.timeouts_total = 0
        self.unavailable_total = 0

    # ------------------------------------------------------------------ recording

    def _slot(self, now: Optional[float] = None) -> _Window:
        start = int((now if now is not None else time.time()) // SLOT_SECONDS) * SLOT_SECONDS
        index = (start // SLOT_SECONDS) % SLOTS
        slot = self._slots[index]
        if slot is None or slot.start != start:
            slot = self._slots[index] = _Window(start)
        return slot

    def _route_key(self, route: str, table: Dict[str, Any]) -> str:
        return route if route in table or len(table) < MAX_ROUTES else OTHER_ROUTE

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        klass = _status_class(status)
        slot = self._slot()
        name = self._route_key(route, slot.routes)
        entry = slot.routes.get(name)
        if entry is None:
            entry = slot.routes[name] = {"count": 0, **{c: 0 for c in STATUS_CLASSES}, "hist": _empty_hist()}
        entry["count"] += 1
        entry[klass] += 1
        entry["hist"][_bucket(seconds)] += 1

        name = self._route_key(route, self.duration_hist)
        key = (method, name, klass)
        self.totals[key] = self.totals.get(key, 0) + 1
        hist = self.duration_hist.get(name)
        if hist is None:
            hist = self.duration_hist[name] = _empty_hist()
        hist[_bucket(seconds)] += 1
        self.duration_sum[name] = self.duration_sum.get(name, 0.0) + seconds

    def started(self) -> None:
        self.in_flight += 1
        if self.in_flight > self.peak_in_flight:
            self.peak_in_flight = self.in_flight

    def finished(self) -> None:
        self.in_flight -= 1

    def shed(self) -> None:
        self.shed_total += 1
        self._slot().shed += 1

    def timed_out(self) -> None:
        self.timeouts_total += 1
        self._slot().timeouts += 1

    def unavailable(self) -> None:
        """A request refused because the database was out of connections or overloaded."""
        self.unavailable_total += 1
        self._slot().unavailable += 1

    # ------------------------------------------------------------------ reading

    def window(self, now: Optional[float] = None) -> Dict[str, Any]:
        """This process's last minute, in the shape instances publish and the fleet view sums."""
        now = now if now is not None else time.time()
        oldest = now - SLOTS * SLOT_SECONDS
        routes: Dict[str, Dict[str, Any]] = {}
        shed = timeouts = unavailable = 0
        for slot in self._slots:
            if slot is None or slot.start <= oldest:
                continue
            shed += slot.shed
            timeouts += slot.timeouts
            unavailable += slot.unavailable
            for name, entry in slot.routes.items():
                _merge_route(routes, name, entry)
        return {
            "instance": INSTANCE_ID,
            "at": now,
            "uptime_seconds": round(now - STARTED_AT),
            "routes": routes,
            "shed": shed,
            "timeouts": timeouts,
            "unavailable": unavailable,
            "in_flight": self.in_flight,
            "peak_in_flight": self.peak_in_flight,
            "loop_lag_ms": round(self.loop_lag_max_ms, 1),
            "db_pool": db_pool_stats(),
            "websockets": websocket_count(),
        }

    def reset(self) -> None:
        self.__init__()  # type: ignore[misc]

    def record_lag(self, lag_ms: float) -> None:
        self.loop_lag_ms = lag_ms
        self.loop_lag_max_ms = max(self.loop_lag_max_ms * 0.9, lag_ms)  # decays over ~a minute


metrics = Metrics()


def _merge_route(into: Dict[str, Dict[str, Any]], name: str, entry: Dict[str, Any]) -> None:
    target = into.get(name)
    if target is None:
        target = into[name] = {"count": 0, **{c: 0 for c in STATUS_CLASSES}, "hist": _empty_hist()}
    target["count"] += entry.get("count", 0)
    for c in STATUS_CLASSES:
        target[c] += entry.get(c, 0)
    for i, n in enumerate(entry.get("hist", [])[: len(target["hist"])]):
        target["hist"][i] += n


def percentile(hist: Sequence[int], q: float) -> Optional[float]:
    """The q-quantile (0..1) of a bucket histogram, in milliseconds, interpolated in its bucket."""
    total = sum(hist)
    if not total:
        return None
    rank = q * total
    seen = 0
    for i, n in enumerate(hist):
        if n and seen + n >= rank:
            low = BUCKETS[i - 1] if i > 0 else 0.0
            high = BUCKETS[i] if i < len(BUCKETS) else BUCKETS[-1] * 2
            return round((low + (high - low) * ((rank - seen) / n)) * 1000, 1)
        seen += n
    return round(BUCKETS[-1] * 2000, 1)


def db_pool_stats() -> Dict[str, Any]:
    try:
        from app.core.database import engine
        from app.core.config import settings

        pool = engine.pool
        return {
            "checked_out": int(pool.checkedout()),  # type: ignore[attr-defined]
            "idle": int(pool.checkedin()),  # type: ignore[attr-defined]
            "limit": settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW,
        }
    except Exception:  # noqa: BLE001 - a pool without counters (tests) reports nothing
        return {}


def websocket_count() -> int:
    try:
        from app.modules.messaging.websocket import manager

        return sum(len(s) for s in manager.active_connections.values())
    except Exception:  # noqa: BLE001
        return 0


def summarize(windows: List[Dict[str, Any]], scope: str) -> Dict[str, Any]:
    """The Traffic tab's numbers from one or more instance windows."""
    routes: Dict[str, Dict[str, Any]] = {}
    hist = _empty_hist()
    totals = {c: 0 for c in STATUS_CLASSES}
    pool_out = pool_limit = 0
    lag = 0.0
    for w in windows:
        lag = max(lag, float(w.get("loop_lag_ms", 0.0)))
        for name, entry in (w.get("routes") or {}).items():
            _merge_route(routes, name, entry)
        pool = w.get("db_pool") or {}
        pool_out += int(pool.get("checked_out", 0))
        pool_limit += int(pool.get("limit", 0))
    for entry in routes.values():
        for i, n in enumerate(entry["hist"]):
            hist[i] += n
        for c in STATUS_CLASSES:
            totals[c] += entry[c]
    requests = sum(totals.values())
    window_seconds = SLOTS * SLOT_SECONDS
    top = sorted(routes.items(), key=lambda kv: kv[1]["count"], reverse=True)[:15]
    return {
        "scope": scope,
        "window_seconds": window_seconds,
        "instances": len(windows),
        "requests": requests,
        "requests_per_second": round(requests / window_seconds, 2),
        "status": totals,
        "error_rate": round(totals["5xx"] / requests, 4) if requests else 0.0,
        "latency_ms": {"p50": percentile(hist, 0.5), "p95": percentile(hist, 0.95), "p99": percentile(hist, 0.99)},
        "shed": sum(int(w.get("shed", 0)) for w in windows),
        "timeouts": sum(int(w.get("timeouts", 0)) for w in windows),
        "unavailable": sum(int(w.get("unavailable", 0)) for w in windows),
        "in_flight": sum(int(w.get("in_flight", 0)) for w in windows),
        "websockets": sum(int(w.get("websockets", 0)) for w in windows),
        "loop_lag_ms": round(lag, 1),
        "db_pool": {"checked_out": pool_out, "limit": pool_limit},
        "routes": [
            {"route": name, "requests": e["count"], "errors": e["5xx"],
             "p95_ms": percentile(e["hist"], 0.95)}
            for name, e in top
        ],
        "per_instance": [
            {"instance": w.get("instance"), "uptime_seconds": w.get("uptime_seconds"),
             "requests": sum(e.get("count", 0) for e in (w.get("routes") or {}).values()),
             "in_flight": w.get("in_flight", 0), "websockets": w.get("websockets", 0),
             "loop_lag_ms": w.get("loop_lag_ms", 0.0),
             "db_pool": w.get("db_pool") or {}}
            for w in sorted(windows, key=lambda x: str(x.get("instance")))
        ],
    }


# ---------------------------------------------------------------------- fleet view (Redis)

async def publish_once() -> bool:
    from app.infrastructure import cache

    client = cache.redis_client
    if client is None:
        return False
    try:
        pipe = client.pipeline()
        pipe.set(FLEET_KEY.format(id=INSTANCE_ID), json.dumps(metrics.window()), ex=PUBLISH_TTL_SECONDS)
        pipe.sadd(FLEET_SET, INSTANCE_ID)
        pipe.expire(FLEET_SET, PUBLISH_TTL_SECONDS * 10)
        await pipe.execute()
        return True
    except Exception:  # noqa: BLE001 - metrics never break the app
        return False


async def publish_forever() -> None:
    """Started at startup; runs until the process stops."""
    while True:
        await publish_once()
        await asyncio.sleep(PUBLISH_EVERY_SECONDS)


async def watch_loop_lag() -> None:
    """Started at startup: measures how late the event loop wakes a timer."""
    loop = asyncio.get_running_loop()
    while True:
        start = loop.time()
        await asyncio.sleep(LAG_PROBE_SECONDS)
        metrics.record_lag(max(0.0, (loop.time() - start - LAG_PROBE_SECONDS) * 1000))


async def fleet_snapshot() -> Dict[str, Any]:
    """Every live instance's last minute, added up. This instance only without Redis."""
    from app.infrastructure import cache

    client = cache.redis_client
    if client is not None:
        try:
            await publish_once()  # include this instance's latest numbers
            ids = sorted(await client.smembers(FLEET_SET))  # type: ignore[misc]
            raw = await client.mget([FLEET_KEY.format(id=i) for i in ids]) if ids else []
            windows, gone = [], []
            for instance, value in zip(ids, raw):
                if value is None:
                    gone.append(instance)
                else:
                    windows.append(json.loads(value))
            if gone:
                await client.srem(FLEET_SET, *gone)  # type: ignore[misc]
            if windows:
                return summarize(windows, "all_instances")
        except Exception:  # noqa: BLE001
            logger.warning("Fleet metrics unavailable; showing this instance only")
    return summarize([metrics.window()], "this_instance")


# ---------------------------------------------------------------------- Prometheus

def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_prometheus() -> str:
    lines = [
        "# HELP flatmate_http_requests_total Requests by method, route template and status class.",
        "# TYPE flatmate_http_requests_total counter",
    ]
    for (method, route, klass), n in sorted(metrics.totals.items()):
        lines.append(f'flatmate_http_requests_total{{method="{method}",route="{_label(route)}",status="{klass}"}} {n}')
    lines += [
        "# HELP flatmate_http_request_duration_seconds Request latency by route template.",
        "# TYPE flatmate_http_request_duration_seconds histogram",
    ]
    for route, hist in sorted(metrics.duration_hist.items()):
        label = _label(route)
        running = 0
        for bound, n in zip(list(BUCKETS) + [float("inf")], hist):
            running += n
            le = "+Inf" if bound == float("inf") else repr(bound)
            lines.append(f'flatmate_http_request_duration_seconds_bucket{{route="{label}",le="{le}"}} {running}')
        lines.append(f'flatmate_http_request_duration_seconds_count{{route="{label}"}} {running}')
        lines.append(f'flatmate_http_request_duration_seconds_sum{{route="{label}"}} {metrics.duration_sum.get(route, 0.0):.6f}')
    pool = db_pool_stats()
    gauges = [
        ("flatmate_http_in_flight_requests", "Requests being handled now.", metrics.in_flight),
        ("flatmate_event_loop_lag_ms", "How late the event loop last woke a timer (ms).", round(metrics.loop_lag_ms, 1)),
        ("flatmate_websocket_connections", "Open realtime sockets on this process.", websocket_count()),
        ("flatmate_db_pool_checked_out", "Database connections in use.", pool.get("checked_out", 0)),
        ("flatmate_db_pool_limit", "Most database connections this process may open.", pool.get("limit", 0)),
    ]
    counters = [
        ("flatmate_http_shed_total", "Requests refused with 503 because the process was full.", metrics.shed_total),
        ("flatmate_http_timeouts_total", "Requests stopped with 504 after REQUEST_TIMEOUT_SECONDS.", metrics.timeouts_total),
        ("flatmate_db_unavailable_total", "Requests refused with 503 because the database was busy.", metrics.unavailable_total),
    ]
    for name, help_text, value in gauges:
        lines += [f"# HELP {name} {help_text}", f"# TYPE {name} gauge", f"{name} {value}"]
    for name, help_text, value in counters:
        lines += [f"# HELP {name} {help_text}", f"# TYPE {name} counter", f"{name} {value}"]
    return "\n".join(lines) + "\n"
