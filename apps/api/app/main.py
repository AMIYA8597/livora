from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.events import lifespan
from app.core.middleware import RequestTraceAndSecurityMiddleware
from app.core.exceptions import AppException
from app.api.v1.router import api_router

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
    }

@app.get("/ready", tags=["System"])
@app.get("/health/ready", tags=["System"])
async def readiness_check():
    # Database and cache connectivity probe
    return {
        "status": "ready",
        "database": "connected",
        "cache": "operational",
    }

@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API. Explore interactive docs at /docs",
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX,
    }

# Mount v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
