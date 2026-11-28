"""Values the API refuses with a 422 instead of failing with a 500: group fields checked up front,
and anything the database itself rejects as too long or out of range (Postgres class 22)."""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.middleware import RequestTraceAndSecurityMiddleware, data_error_code, is_data_error
from app.modules.groups.schemas import GroupCreate, GroupResponse
from tests.conftest import TEST_DATABASE_URL


def _group(**overrides):
    base = {"name": "Koramangala 3BHK seekers", "target_city": "Bengaluru", "target_budget_total": 45000}
    base.update(overrides)
    return base


def test_a_normal_group_is_accepted():
    group = GroupCreate(**_group(name="  HSR seekers ", target_move_in=str(date.today() + timedelta(days=20))))
    assert group.name == "HSR seekers"


@pytest.mark.parametrize("overrides", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 121},
    {"target_city": ""}, {"target_city": "x" * 101},
    {"description": "y" * 2001},
    {"target_budget_total": 0}, {"target_budget_total": -100}, {"target_budget_total": 10_000_001},
    {"target_move_in": "2020-01-01"}, {"target_move_in": str(date.today() + timedelta(days=731))},
])
def test_bad_group_fields_are_refused(overrides):
    with pytest.raises(ValidationError):
        GroupCreate(**_group(**overrides))


def test_stored_groups_still_read_back():
    now = "2026-01-01T00:00:00Z"
    GroupResponse(id="00000000-0000-4000-8000-000000000001", name="", target_city="", target_budget_total=0,
                  target_move_in=date(2020, 1, 1), created_at=now, updated_at=now)


@pytest.mark.asyncio
async def test_a_database_data_exception_is_recognised():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("create temp table short_names (name varchar(3))"))
                await conn.execute(text("insert into short_names values (:name)"), {"name": "too long"})
        except DBAPIError as error:
            assert data_error_code(error) == "22001" and is_data_error(error)
        except OSError:
            pytest.skip("needs the test database")
        else:
            pytest.fail("the cast should have failed")
    finally:
        await engine.dispose()


class _Orig(Exception):
    def __init__(self, sqlstate):
        super().__init__("db said no")
        self.sqlstate = sqlstate


class _DbError(Exception):
    def __init__(self, sqlstate):
        super().__init__("wrapped")
        self.orig = _Orig(sqlstate)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestTraceAndSecurityMiddleware)

    @app.get("/too-long")
    async def too_long():
        raise _DbError("22001")

    @app.get("/other")
    async def other():
        raise _DbError("23505")

    return app


@pytest.mark.asyncio
async def test_a_value_the_database_refuses_is_a_422_not_a_500():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://t") as client:
        resp = await client.get("/too-long")
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "INVALID_VALUE" and resp.headers["X-Request-ID"]
        # Any other database error is still a server error.
        assert (await client.get("/other")).status_code == 500
