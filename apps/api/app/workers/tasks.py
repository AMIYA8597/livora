"""
Celery tasks. Each run uses its own event loop and a NullPool engine: asyncpg
connections are bound to the loop that created them, so pooled connections must
never outlive a single `asyncio.run`.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Awaitable, Callable, Dict, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import engine_options
from app.workers.celery_app import celery_app
from app.workers.maintenance import run_maintenance
from app.workers.outbox import dispatch_pending

T = TypeVar("T")

POOL_KEYS = {"pool_size", "max_overflow"}


def run_with_session_factory(job: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]]) -> T:
    async def runner() -> T:
        options = {k: v for k, v in engine_options(settings.DATABASE_URL).items() if k not in POOL_KEYS}
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, **options)
        try:
            return await job(async_sessionmaker(bind=engine, expire_on_commit=False))
        finally:
            await engine.dispose()

    return asyncio.run(runner())


@celery_app.task(name="outbox.dispatch", ignore_result=True)
def dispatch_outbox() -> Dict[str, Any]:
    return asdict(run_with_session_factory(dispatch_pending))


@celery_app.task(name="maintenance.run", ignore_result=True)
def maintenance() -> Dict[str, int]:
    return run_with_session_factory(run_maintenance)
