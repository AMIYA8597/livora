from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.cache import init_redis, close_redis
from app.infrastructure.storage import init_storage

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections
    await init_redis()
    init_storage()
    yield
    # Shutdown: gracefully close connections
    await close_redis()
