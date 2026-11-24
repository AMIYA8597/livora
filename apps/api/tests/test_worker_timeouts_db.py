"""
Worker jobs and the API login's statement limits, against a real database.

The test login carries the production limits (15s per statement, 30s idle in a transaction;
see conftest and scripts/create_app_db_user.sql). Maintenance and ranker training raise them
with SET LOCAL in every transaction; the outbox sweep keeps them.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.workers import tasks


async def _limits(session_factory):
    seen = []
    for _ in range(2):  # every transaction, not just the first
        async with session_factory() as db:
            seen.append((
                (await db.execute(text("SHOW statement_timeout"))).scalar_one(),
                (await db.execute(text("SHOW idle_in_transaction_session_timeout"))).scalar_one(),
            ))
    return seen


def test_jobs_without_an_override_keep_the_api_limits():
    assert tasks.run_with_session_factory(_limits) == [("15s", "30s")] * 2


def test_long_jobs_get_the_worker_limit_in_every_transaction():
    assert settings.WORKER_STATEMENT_TIMEOUT_SECONDS == 600
    assert tasks.run_with_session_factory(_limits, 600) == [("10min", "10min")] * 2


def test_the_override_is_really_enforced():
    async def slow(session_factory):
        async with session_factory() as db:
            await db.execute(text("SELECT pg_sleep(2)"))

    with pytest.raises(DBAPIError, match="statement timeout"):
        tasks.run_with_session_factory(slow, 1)


def test_scheduled_long_jobs_use_the_worker_limit(monkeypatch):
    from app.workers.outbox import DispatchResult

    calls = []

    def fake(job, timeout=None):
        calls.append(timeout)
        return DispatchResult()

    monkeypatch.setattr(tasks, "run_with_session_factory", fake)
    tasks.maintenance()
    tasks.train_ranker()
    tasks.dispatch_outbox()
    assert calls == [600, 600, None]  # the outbox sweep keeps the API's limits


def test_timeout_must_be_positive():
    with pytest.raises(ValueError):
        tasks.timeout_statements(0)
