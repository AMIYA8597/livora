from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.cache import init_redis, close_redis
from app.infrastructure.storage import init_storage
from app.infrastructure.email import init_email_provider

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections
    await init_redis()
    init_storage()
    init_email_provider()
    yield
    # Shutdown: gracefully close connections
    await close_redis()
