from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.cache import init_redis, close_redis
from app.infrastructure.storage import init_storage
from app.infrastructure.email import init_email_provider
from app.infrastructure.sms import init_sms_provider
from app.core.database import warn_if_overprivileged
from app.core.security import require_signing_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    require_signing_key()
    # Startup: initialize connections
    await init_redis()
    init_storage()
    init_email_provider()
    init_sms_provider()
    await warn_if_overprivileged()
    yield
    # Shutdown: gracefully close connections
    await close_redis()
