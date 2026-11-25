import asyncio
import contextlib
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
    from app.core.metrics import publish_forever, watch_loop_lag

    # The admin Traffic tab's fleet view, and the event-loop delay it shows.
    background = [asyncio.create_task(publish_forever()), asyncio.create_task(watch_loop_lag())]
    yield
    # Shutdown: gracefully close connections
    for task in background:
        task.cancel()
    for task in background:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await close_redis()
