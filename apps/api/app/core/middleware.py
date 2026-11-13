"""
Application Middleware: Request ID tracing, execution timing, security headers,
content length payload limits, and standard RFC 7807 Problem Details error formatting.
"""

import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.exceptions import AppException
from app.core.logging import logger

# Maximum allowed request body size in bytes (10 Megabytes)
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


class RequestTraceAndSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate or extract correlation Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.perf_counter()

        # 2. Enforce Request Body Payload Size Limit (DoS Protection)
        content_length_header = request.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > MAX_REQUEST_BODY_BYTES:
                    logger.warning(
                        f"[Req {request_id}] Payload too large: {content_length} bytes > max {MAX_REQUEST_BODY_BYTES}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "type": "https://errors.flatmate.platform/payload_too_large",
                            "title": "Payload Too Large",
                            "status": 413,
                            "detail": f"Request body size {content_length} bytes exceeds maximum allowed limit of {MAX_REQUEST_BODY_BYTES} bytes.",
                            "instance": request.url.path,
                            "request_id": request_id,
                        },
                        media_type="application/problem+json",
                    )
            except ValueError:
                pass

        try:
            response: Response = await call_next(request)
        except AppException as app_exc:
            return app_exc.to_problem_response(request)
        except Exception as exc:
            logger.error(f"[Req {request_id}] Unhandled exception: {exc}", exc_info=True)
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

        # 3. Defense-in-depth Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Log request summary
        logger.info(
            f"{request.method} {request.url.path} [{response.status_code}] ({duration_ms}ms) req_id={request_id}"
        )
        return response
