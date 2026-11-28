"""
Database round trips. The API server and the database are in different regions, so every
round trip costs ~90 ms: requests must not spend them on four-step pings, statement closes,
or a second query for the signed-in user's roles. Each response reports its statement count.
"""
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import (
    QueryStats,
    engine_options,
    install_ping,
    install_query_stats,
    ping_on_checkout,
    query_stats_var,
)
from tests.conftest import TEST_DATABASE_URL

POOLED = "postgresql+asyncpg://u:p@h:6543/db"


class _Driver:
    def __init__(self, fail: bool = False):
        self.calls = []
        self.fail = fail

    async def execute(self, query, timeout=None):
        self.calls.append(query)
        if self.fail:
            raise ConnectionResetError("gone")


class _Adapted:
    def __init__(self, driver):
        self.driver_connection = driver


class _Record:
    def __init__(self, fresh: bool):
        self.info = {"fresh": True} if fresh else {}


def test_ping_skips_a_connection_opened_for_this_checkout():
    driver = _Driver()
    record = _Record(fresh=True)
    ping_on_checkout(_Adapted(driver), record, None)
    assert driver.calls == [] and "fresh" not in record.info


@pytest.mark.asyncio
async def test_ping_is_one_empty_query_and_a_failure_invalidates_the_pool():
    from sqlalchemy.exc import InvalidatePoolError
    from sqlalchemy.util import greenlet_spawn

    driver = _Driver()
    await greenlet_spawn(ping_on_checkout, _Adapted(driver), _Record(fresh=False), None)
    assert driver.calls == ["SELECT 1"]

    with pytest.raises(InvalidatePoolError):
        await greenlet_spawn(ping_on_checkout, _Adapted(_Driver(fail=True)), _Record(fresh=False), None)


@pytest.mark.asyncio
async def test_pool_keeps_a_healthy_connection_across_checkouts():
    """The ping must pass on a live connection: a failing ping silently reconnects on every
    request (TLS and sign-in, ~600 ms), which is how an empty-query ping once shipped."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    install_ping(engine.sync_engine)
    invalidated = []
    event.listen(engine.sync_engine, "invalidate", lambda *args: invalidated.append(args[-1]))
    try:
        pids = []
        try:
            for _ in range(3):
                async with engine.connect() as conn:
                    pids.append((await conn.execute(text("select pg_backend_pid()"))).scalar_one())
        except OSError:
            pytest.skip("needs the test database")
        assert invalidated == [] and len(set(pids)) == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pool_replaces_a_dead_connection_on_checkout():
    """The server ended the pooled connection (a restart, an idle timeout): the next checkout
    gets a working one instead of an error."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    install_ping(engine.sync_engine)
    killer = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        try:
            async with engine.connect() as conn:
                pid = (await conn.execute(text("select pg_backend_pid()"))).scalar_one()
        except OSError:
            pytest.skip("needs the test database")
        async with killer.connect() as conn:
            await conn.execute(text("select pg_terminate_backend(:pid)"), {"pid": pid})
        async with engine.connect() as conn:
            again = (await conn.execute(text("select pg_backend_pid()"))).scalar_one()
        assert again != pid
    finally:
        await engine.dispose()
        await killer.dispose()


@pytest.mark.asyncio
async def test_unnamed_statements_run_queries_back_to_back():
    """The pooler options (unnamed statements, no caches) against a real server: parameterised
    statements one after another, including types asyncpg has to look up first (jsonb, arrays)."""
    options = engine_options(POOLED)
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, connect_args=options["connect_args"])
    try:
        try:
            async with engine.begin() as conn:
                for n in range(3):
                    assert (await conn.execute(text("select :n + 1"), {"n": n})).scalar_one() == n + 1
                row = (await conn.execute(
                    text("select cast(:j as jsonb) ->> 'a', cast(:arr as int[])"),
                    {"j": '{"a": "x"}', "arr": [1, 2]},
                )).one()
                assert row[0] == "x" and list(row[1]) == [1, 2]
                assert (await conn.execute(text("select :s"), {"s": "again"})).scalar_one() == "again"
        except OSError:
            pytest.skip("needs the test database")
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_query_stats_count_statements():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    install_query_stats(engine.sync_engine)
    stats = QueryStats()
    token = query_stats_var.set(stats)
    try:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("select 1"))
                await conn.execute(text("select 2"))
        except OSError:
            pytest.skip("needs the test database")
    finally:
        query_stats_var.reset(token)
        await engine.dispose()
    assert stats.count == 2 and stats.seconds > 0


@pytest.mark.asyncio
async def test_signed_in_user_costs_one_statement(async_client: AsyncClient):
    """Every response reports its statement count. Loading the signed-in user, roles included,
    is a single statement: /notifications/unread-count is that plus its own count."""
    email = f"rt_{uuid4().hex[:10]}@example.in"
    resp = await async_client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": "Round Trip", "role": "seeker",
    })
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    me = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert "seeker" in str(me.json())
    assert int(me.headers["X-DB-Queries"]) >= 1 and float(me.headers["X-DB-Time-Ms"]) >= 0

    unread = await async_client.get("/api/v1/notifications/unread-count", headers=headers)
    assert unread.status_code == 200
    assert int(unread.headers["X-DB-Queries"]) == 2

    health = await async_client.get("/health")
    assert health.headers["X-DB-Queries"] == "0"


@pytest.mark.asyncio
async def test_a_like_and_a_like_back_make_a_match_in_few_statements(async_client: AsyncClient):
    """Liking loads both people's earlier decisions in one query and both profiles in another,
    and a like back reuses the score it just worked out instead of computing it again."""
    async def register(name: str) -> tuple[dict, str]:
        resp = await async_client.post("/api/v1/auth/register", json={
            "email": f"lk_{uuid4().hex[:10]}@example.in", "password": "Password123!",
            "full_name": name, "role": "seeker",
        })
        assert resp.status_code == 201, resp.text
        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        me = (await async_client.get("/api/v1/auth/me", headers=headers)).json()
        return headers, me["id"]

    asha, asha_id = await register("Asha Like")
    ravi, ravi_id = await register("Ravi Like")

    first = await async_client.post("/api/v1/matching/interactions", headers=asha,
                                    json={"target_user_id": ravi_id, "action": "like"})
    assert first.status_code == 200, first.text
    assert first.json()["is_mutual_match"] is False
    assert int(first.headers["X-DB-Queries"]) <= 10  # was 14

    back = await async_client.post("/api/v1/matching/interactions", headers=ravi,
                                   json={"target_user_id": asha_id, "action": "like"})
    assert back.status_code == 200, back.text
    body = back.json()
    assert body["is_mutual_match"] is True and body["mutual_match_id"]
    assert body["compatibility_score"] is not None
    assert int(back.headers["X-DB-Queries"]) <= 16  # was 21

    again = await async_client.post("/api/v1/matching/interactions", headers=asha,
                                    json={"target_user_id": ravi_id, "action": "like"})
    assert again.status_code == 200 and again.json()["mutual_match_id"] == body["mutual_match_id"]
    assert int(again.headers["X-DB-Queries"]) <= 11
