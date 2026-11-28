"""
Application Middleware: Request ID tracing, execution timing, security headers,
content length payload limits, and standard RFC 7807 Problem Details error formatting.
"""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.client_version import is_exempt, upgrade_required
from app.core.database import QueryStats, query_stats_var
from app.core.exceptions import AppException
from app.core.logging import clean_request_id, cloud_trace, logger, request_id_var, trace_var
from app.core.observability import tag_request
from app.core.overload import busy_response

# Maximum allowed request body size in bytes (10 Megabytes)
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024
# File uploads (largest bucket limit is 15 MB) plus multipart framing; each route then enforces
# its own bucket limit while reading.
MAX_UPLOAD_BODY_BYTES = 16 * 1024 * 1024
UPLOAD_PATH_SUFFIXES = ("/storage/upload", "/attachments")


def body_limit_for(path: str) -> int:
    return MAX_UPLOAD_BODY_BYTES if path.rstrip("/").endswith(UPLOAD_PATH_SUFFIXES) else MAX_REQUEST_BODY_BYTES


def data_error_code(exc: BaseException) -> str | None:
    """The SQLSTATE of a database error anywhere in the exception's chain, if any."""
    seen = 0
    current: BaseException | None = exc
    while current is not None and seen < 5:
        code = getattr(getattr(current, "orig", None), "sqlstate", None) or getattr(current, "sqlstate", None)
        if isinstance(code, str):
            return code
        current = current.__cause__ or current.__context__
        seen += 1
    return None


def is_data_error(exc: BaseException) -> bool:
    """Postgres class 22, "data exception": a value too long for its column (22001), a number
    out of range (22003), an impossible date (22008) and the like. The caller sent it."""
    code = data_error_code(exc)
    return bool(code) and code.startswith("22")


class RequestTraceAndSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Correlation ID: reuse the caller's only if it's safe to put in a log line.
        request_id = clean_request_id(request.headers.get("X-Request-ID")) or str(uuid.uuid4())
        request.state.request_id = request_id
        rid_token = request_id_var.set(request_id)
        trace_token = trace_var.set(cloud_trace(request.headers.get("X-Cloud-Trace-Context")))
        tag_request(request_id)
        start_time = time.perf_counter()
        # Shared by reference with the endpoint's task, which runs in a copy of this context.
        stats = QueryStats()
        stats_token = query_stats_var.set(stats)
        try:
            response = await self._handle(request, call_next, request_id, start_time)
            response.headers["X-DB-Queries"] = str(stats.count)
            response.headers["X-DB-Time-Ms"] = str(round(stats.seconds * 1000, 2))
            return response
        finally:
            query_stats_var.reset(stats_token)
            request_id_var.reset(rid_token)
            trace_var.reset(trace_token)

    async def _handle(self, request: Request, call_next, request_id: str, start_time: float):

        # 2. Enforce Request Body Payload Size Limit (DoS Protection)
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                limit = body_limit_for(request.url.path)
                if content_length > limit:
                    logger.warning(f"[Req {request_id}] Payload too large: {content_length} bytes > max {limit}")
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "https://errors.flatmate.platform/payload_too_large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request body size {content_length} bytes exceeds maximum allowed limit of {limit} bytes.",
                            "instance": request.url.path,
                            "request_id": request_id,
                        },
                        media_type="application/problem+json",
                    )
            except ValueError:
                pass

        # 3. Mobile apps too old for this API are told to update (see app/core/client_version.py).
        if not is_exempt(request.url.path):
            upgrade = upgrade_required(request.headers.get("X-Client-Platform"), request.headers.get("X-Client-Version"))
            if upgrade is not None:
                return JSONResponse(
                    status_code=426,
                    content={
                        "type": "https://errors.flatmate.platform/client_upgrade_required",
                        "title": "Upgrade Required",
                        "status": 426,
                        "detail": "This version of the app is no longer supported. Please update to continue.",
                        "error_code": "CLIENT_UPGRADE_REQUIRED",
                        "instance": request.url.path,
                        "request_id": request_id,
                        "min_version": upgrade["min_version"],
                        "update_url": upgrade["update_url"],
                    },
                    media_type="application/problem+json",
                    headers={"X-Request-ID": request_id},
                )

        try:
            response: Response = await call_next(request)
        except AppException as app_exc:
            return app_exc.to_problem_response(request)
        except Exception as exc:
            # Out of database connections, or the database is overloaded: "busy, retry", not a bug.
            busy = busy_response(exc, request.url.path, request_id)
            if busy is not None:
                busy.headers["X-Request-ID"] = request_id
                return busy
            # A value the database refused (too long for its column, a number out of range):
            # the request was wrong, so say so with a 422, not a 500.
            if is_data_error(exc):
                logger.warning(f"Rejected value on {request.method} {request.url.path}: {data_error_code(exc)}")
                return JSONResponse(
                    status_code=422,
                    content={
                        "type": "https://errors.flatmate.platform/invalid_value",
                        "title": "Invalid Value",
                        "status": 422,
                        "detail": "One of the values sent is too long or out of range.",
                        "error_code": "INVALID_VALUE",
                        "instance": request.url.path,
                        "request_id": request_id,
                    },
                    media_type="application/problem+json",
                    headers={"X-Request-ID": request_id},
                )
            # Logged with the traceback; with Sentry on, this is what reports the error.
            logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {type(exc).__name__}")
            return JSONResponse(
                status_code=500,
                content={
                    "type": "https://errors.flatmate.platform/internal-error",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected server error occurred. Please contact support with the request ID.",
                    "instance": request.url.path,
                    "request_id": request_id,
                },
                media_type="application/problem+json",
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)

        # 4. Defense-in-depth Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Request summary (path only: query strings can carry tokens).
        status = response.status_code
        # At most WARNING: an unhandled error was already logged (and reported) with its traceback.
        log = logger.warning if status >= 400 and status != 404 else logger.info
        log(
            f"{request.method} {request.url.path} [{status}] ({duration_ms}ms) req_id={request_id}",
            extra={"fields": {"http": {"method": request.method, "path": request.url.path,
                                       "status": status, "duration_ms": duration_ms}}},
        )
        return response
