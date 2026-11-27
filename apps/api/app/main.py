import asyncio
import hmac
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.core.observability import init_sentry
from app.core.events import lifespan
from app.core.middleware import RequestTraceAndSecurityMiddleware
from app.core.overload import OverloadGuard
from app.core.exceptions import AppException
from app.api.v1.router import api_router

init_sentry("api")


def docs_urls(environment: str | None) -> dict:
    """Swagger UI, ReDoc and the OpenAPI schema are public everywhere except production, where
    they would hand anyone a map of every endpoint. The schema is still built in code
    (`app.openapi()`) for the contract checks; only the URLs go away."""
    if (environment or "").strip().lower() in {"production", "prod"}:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="India-First Flatmate Compatibility & Rental Marketplace API",
    version="1.0.0",
    **docs_urls(settings.ENVIRONMENT),
    lifespan=lifespan,
)

# Custom RFC 7807 Exception Handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return exc.to_problem_response(request)

# Middlewares, innermost first: tracing and security headers, then overload protection and
# request metrics (app/core/overload.py), then CORS outermost so even a "busy" 503 is readable
# by the browser.
app.add_middleware(RequestTraceAndSecurityMiddleware)
app.add_middleware(OverloadGuard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms", "X-DB-Queries", "X-DB-Time-Ms"],
)

# Root Health & Readiness Checks
@app.get("/health", tags=["System"])
@app.get("/health/live", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
        "release": settings.APP_RELEASE,
    }

async def _check_database() -> None:
    from app.core.database import engine

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis() -> str:
    from app.infrastructure import cache

    if cache.redis_client is None:
        return "unavailable"
    await cache.redis_client.ping()
    return "ok"


@app.get("/ready", tags=["System"])
@app.get("/health/ready", tags=["System"])
async def readiness_check(response: Response):
    """Ready to serve: the database must answer. Redis is reported but optional (the app runs
    without it: cache bypass, single-instance realtime), so it never fails readiness."""
    checks: dict = {}
    start = time.perf_counter()
    try:
        await asyncio.wait_for(_check_database(), timeout=3)
        checks["database"] = {"status": "ok", "ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Readiness: database check failed ({type(exc).__name__})")
        checks["database"] = {"status": "error"}
    start = time.perf_counter()
    try:
        state = await asyncio.wait_for(_check_redis(), timeout=1)
        checks["redis"] = {"status": state, "ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Readiness: redis check failed ({type(exc).__name__})")
        checks["redis"] = {"status": "error"}

    ready = checks["database"]["status"] == "ok"
    response.status_code = 200 if ready else 503
    response.headers["Cache-Control"] = "no-store"
    return {"status": "ready" if ready else "not_ready", "release": settings.APP_RELEASE, "checks": checks}

@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request):
    """Prometheus text for this process (app/core/metrics.py). Exists only when METRICS_TOKEN is
    set, and needs it as a bearer token."""
    from app.core.metrics import render_prometheus

    token = settings.METRICS_TOKEN
    supplied = request.headers.get("authorization", "")
    if not token:
        return PlainTextResponse("Not Found", status_code=404)
    if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
        return PlainTextResponse("Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"})
    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4",
                             headers={"Cache-Control": "no-store"})


@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API. Explore interactive docs at /docs",
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }

# Mount v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
