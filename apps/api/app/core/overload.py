"""
Overload protection: when there's more traffic than an instance can serve, answer quickly and
honestly ("busy, retry in N seconds") instead of queueing until every request is slow, running
out of memory, or failing with 500s.

`OverloadGuard` (outermost app middleware inside CORS, so refusals still carry CORS headers):
  * Load shedding: past MAX_IN_FLIGHT_REQUESTS concurrent requests on this process, new ones
    get 503 with Retry-After at once. Health checks are never refused (a probe failing under load
    would get a healthy instance restarted, making things worse); WebSockets aren't counted
    (they're long-lived and idle most of the time).
  * Deadline: a request still running after REQUEST_TIMEOUT_SECONDS is stopped with 504, so a
    stuck query or provider call can't hold its slot and connection forever. Uploads are exempt.
  * Measures every request for app/core/metrics.py.

`busy_response(exc)`: database errors that mean "busy, not broken" (pool exhausted, too many
connections, server starting, statement timeout) become 503 with Retry-After instead of 500.

The web client retries 503s that carry Retry-After for reads (apps/web/lib/api-client.ts).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Awaitable, Callable, MutableMapping, Optional

from app.core.config import settings
from app.core.metrics import metrics

logger = logging.getLogger("flatmate.overload")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# Never shed, never time out: liveness/readiness and the metrics scrape.
EXEMPT_PATHS = frozenset({"/", "/health", "/health/live", "/ready", "/health/ready", "/metrics"})
NO_DEADLINE_SUFFIXES = ("/storage/upload", "/attachments")

# Postgres SQLSTATEs that mean "busy": too_many_connections, cannot_connect_now, query_canceled
# (statement_timeout), admin_shutdown, crash_shutdown.
BUSY_SQLSTATES = frozenset({"53300", "57P03", "57014", "57P01", "57P02"})
BUSY_ERROR_NAMES = frozenset({
    "TooManyConnectionsError", "CannotConnectNowError", "QueryCanceledError",
    "ConnectionDoesNotExistError", "AdminShutdownError",
})


def retry_after_seconds(base: int = 2) -> int:
    """A small random spread so refused clients don't all come back in the same second."""
    return base + random.randint(0, 2)


def problem_body(status: int, title: str, detail: str, error_code: str, path: str) -> bytes:
    return json.dumps({
        "type": f"https://errors.flatmate.platform/{error_code.lower()}",
        "title": title,
        "status": status,
        "detail": detail,
        "error_code": error_code,
        "instance": path,
    }).encode()


async def _send_problem(send: Send, status: int, body: bytes, retry_after: Optional[int]) -> None:
    headers = [(b"content-type", b"application/problem+json"), (b"content-length", str(len(body)).encode()),
               (b"cache-control", b"no-store")]
    if retry_after is not None:
        headers.append((b"retry-after", str(retry_after).encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _route_of(scope: Scope) -> str:
    """The full route template (`/api/v1/properties/{property_id}`): the request path with each
    path parameter's segment put back as `{name}`. Included routers keep only their own part of
    the template on the route, so it's rebuilt from the path. Unrouted paths (404s) share one name,
    so scanners can't create unbounded series."""
    if scope.get("route") is None:
        return "(unmatched)"
    path: str = scope.get("path", "")
    params = scope.get("path_params") or {}
    if not params:
        return path
    by_value = {str(v): k for k, v in params.items()}
    return "/".join(f"{{{by_value[seg]}}}" if seg in by_value else seg for seg in path.split("/"))


class OverloadGuard:
    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        limit = settings.MAX_IN_FLIGHT_REQUESTS
        if limit and metrics.in_flight >= limit:
            metrics.shed()
            metrics.observe(method, "(shed)", 503, 0.0)
            await _send_problem(send, 503, problem_body(
                503, "Server Busy", "We're handling a lot of requests right now. Please try again in a moment.",
                "SERVER_BUSY", path), retry_after_seconds())
            return

        status: dict = {"code": None}

        async def send_tracking(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        deadline = None if path.rstrip("/").endswith(NO_DEADLINE_SUFFIXES) else settings.REQUEST_TIMEOUT_SECONDS
        metrics.started()
        start = time.perf_counter()
        try:
            if deadline is None:
                await self.app(scope, receive, send_tracking)
            else:
                timer = asyncio.timeout(deadline)
                try:
                    async with timer:
                        await self.app(scope, receive, send_tracking)
                except TimeoutError:
                    if not timer.expired():
                        raise  # the app's own timeout error, not our deadline
                    metrics.timed_out()
                    logger.warning("Request stopped after %ss: %s %s", deadline, method, _route_of(scope))
                    if status["code"] is None:
                        status["code"] = 504
                        await _send_problem(send, 504, problem_body(
                            504, "Request Timed Out", "This took too long. Please try again.",
                            "REQUEST_TIMEOUT", path), None)
        finally:
            metrics.finished()
            metrics.observe(method, _route_of(scope), status["code"] or 500, time.perf_counter() - start)


def _chain(exc: BaseException):
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = getattr(current, "orig", None) or current.__cause__ or current.__context__


def is_busy_error(exc: BaseException) -> bool:
    """True for database errors that mean "too busy right now", not a bug."""
    from sqlalchemy import exc as sa_exc

    if isinstance(exc, sa_exc.TimeoutError):  # pool exhausted for DB_POOL_TIMEOUT_SECONDS
        return True
    for err in _chain(exc):
        if type(err).__name__ in BUSY_ERROR_NAMES:
            return True
        code = getattr(err, "sqlstate", None) or getattr(err, "pgcode", None)
        if isinstance(code, str) and code in BUSY_SQLSTATES:
            return True
        if isinstance(err, (ConnectionRefusedError, ConnectionResetError)):
            return True
    return False


def busy_response(exc: BaseException, path: str, request_id: str):
    """A 503 response for a busy-database error, or None for anything else."""
    if not is_busy_error(exc):
        return None
    from starlette.responses import Response

    metrics.unavailable()
    logger.warning("Database busy (%s): answered 503", type(exc).__name__)
    body = json.loads(problem_body(
        503, "Service Busy", "We're very busy right now. Please try again in a moment.",
        "SERVICE_BUSY", path))
    body["request_id"] = request_id
    return Response(
        content=json.dumps(body), status_code=503, media_type="application/problem+json",
        headers={"Retry-After": str(retry_after_seconds()), "Cache-Control": "no-store"},
    )
