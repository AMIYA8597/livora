"""
Celery tasks. Each run uses its own event loop and a NullPool engine: asyncpg
connections are bound to the loop that created them, so pooled connections must
never outlive a single `asyncio.run`.

The database login carries the API's limits (scripts/create_app_db_user.sql: 15s per statement,
30s idle in a transaction). Maintenance and ranker training can legitimately take longer, so
they raise both to WORKER_STATEMENT_TIMEOUT_SECONDS with `SET LOCAL` at the start of every
transaction. SET LOCAL, unlike a session setting or a startup parameter, is safe behind
Supabase's transaction pooler: it ends with the transaction and never leaks to another client.
The outbox sweep keeps the API's limits; its handlers are short.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import engine_options
from app.workers.celery_app import celery_app
from app.workers.maintenance import run_maintenance
from app.workers.outbox import dispatch_pending

T = TypeVar("T")

POOL_KEYS = {"pool_size", "max_overflow"}


def timeout_statements(seconds: int) -> list[str]:
    seconds = int(seconds)
    if seconds <= 0:
        raise ValueError("statement timeout must be positive")
    return [
        f"SET LOCAL statement_timeout = '{seconds}s'",
        f"SET LOCAL idle_in_transaction_session_timeout = '{seconds}s'",
    ]


def run_with_session_factory(
    job: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]],
    statement_timeout_seconds: Optional[int] = None,
) -> T:
    async def runner() -> T:
        options = {k: v for k, v in engine_options(settings.DATABASE_URL).items() if k not in POOL_KEYS}
        engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, **options)
        if statement_timeout_seconds:
            statements = timeout_statements(statement_timeout_seconds)

            @event.listens_for(engine.sync_engine, "begin")
            def _longer_limits(conn) -> None:
                for statement in statements:
                    conn.exec_driver_sql(statement)

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
    return run_with_session_factory(run_maintenance, settings.WORKER_STATEMENT_TIMEOUT_SECONDS)


@celery_app.task(name="ml.train_listing_ranker", ignore_result=True)
def train_listing_ranker() -> Dict[str, Any]:
    """Weekly: retrain the listing ranker; it activates only if it beats the weighted score."""
    from app.ml.training import train_listing_ranker as run_training

    async def job(session_factory: async_sessionmaker[AsyncSession]) -> Dict[str, Any]:
        async with session_factory() as db:
            report = await run_training(db)
        return {"rows": report.rows, "activated": report.activated, "version": report.version,
                "reason": report.reason}

    return run_with_session_factory(job, settings.WORKER_STATEMENT_TIMEOUT_SECONDS)


@celery_app.task(name="ml.train_ranker", ignore_result=True)
def train_ranker() -> Dict[str, Any]:
    """Weekly: retrain the like/pass ranker; it activates only if it beats the heuristic."""
    from app.ml.training import train_ranker as run_training

    async def job(session_factory: async_sessionmaker[AsyncSession]) -> Dict[str, Any]:
        async with session_factory() as db:
            report = await run_training(db)
        return {"rows": report.rows, "activated": report.activated, "version": report.version,
                "reason": report.reason}

    return run_with_session_factory(job, settings.WORKER_STATEMENT_TIMEOUT_SECONDS)
