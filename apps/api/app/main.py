import asyncio
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.core.observability import init_sentry
from app.core.events import lifespan
from app.core.middleware import RequestTraceAndSecurityMiddleware
from app.core.exceptions import AppException
from app.api.v1.router import api_router

init_sentry("api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="India-First Flatmate Compatibility & Rental Marketplace API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Custom RFC 7807 Exception Handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return exc.to_problem_response(request)

# Custom Middlewares
app.add_middleware(RequestTraceAndSecurityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
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

@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API. Explore interactive docs at /docs",
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }

# Mount v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
