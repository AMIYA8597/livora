import sys
from pathlib import Path

# Add apps/api to sys.path so 'app' can be resolved regardless of execution root
api_root = str(Path(__file__).resolve().parent.parent)
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import os
from urllib.parse import urlparse

# Tests must never run against a hosted/production database. Force an isolated local
# database BEFORE the app (and its settings) are imported; real env vars take precedence
# over the .env file in pydantic-settings, so this overrides apps/api/.env.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/flatmate_test",
)
_test_db_host = urlparse(TEST_DATABASE_URL.replace("+asyncpg", "")).hostname
if _test_db_host not in {"localhost", "127.0.0.1", "::1", "postgres"}:
    raise RuntimeError(
        f"Refusing to run tests against non-local database host '{_test_db_host}'. "
        "Set TEST_DATABASE_URL to a disposable local database."
    )


def _provision_app_login(owner_url: str) -> str:
    """
    Run the suite as a least-privilege login (member of `flatmate_app`, migration 007), exactly
    like production, so any code path that needs owner/DDL rights fails in tests.
    Set TEST_DB_AS_OWNER=1 to run as the owner instead (debugging only).
    """
    import asyncio
    from urllib.parse import urlsplit, urlunsplit

    import asyncpg

    user, password = "flatmate_api_test", "flatmate_api_test"

    async def provision() -> None:
        conn = await asyncpg.connect(owner_url.replace("+asyncpg", ""))
        try:
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app'"):
                raise RuntimeError(
                    "Role flatmate_app is missing in the test database: run `alembic upgrade head` "
                    "against TEST_DATABASE_URL first."
                )
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", user):
                await conn.execute(f"CREATE ROLE {user} LOGIN PASSWORD '{password}' IN ROLE flatmate_app")
            # The same limits scripts/create_app_db_user.sql puts on the production login.
            await conn.execute(f"ALTER ROLE {user} SET statement_timeout = '15s'")
            await conn.execute(f"ALTER ROLE {user} SET idle_in_transaction_session_timeout = '30s'")
        finally:
            await conn.close()

    asyncio.run(provision())
    parts = urlsplit(owner_url)
    host = parts.hostname or "localhost"
    netloc = f"{user}:{password}@{host}" + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


OWNER_DATABASE_URL = TEST_DATABASE_URL
os.environ["MIGRATION_DATABASE_URL"] = OWNER_DATABASE_URL
os.environ["DATABASE_URL"] = (
    TEST_DATABASE_URL if os.environ.get("TEST_DB_AS_OWNER") == "1" else _provision_app_login(TEST_DATABASE_URL)
)
os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_TYPE"] = "local"  # never upload to hosted buckets from tests
os.environ["EMAIL_PROVIDER"] = "memory"  # never send real mail from tests
os.environ["GEOCODER"] = "off"  # never call OpenStreetMap from tests (geocoding tests inject a fake)

import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import engine

@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def reset_rate_limits():
    """Every test starts with fresh rate-limit counts (all test calls share one client IP)."""
    from app.core import rate_limit

    await rate_limit.reset()
    yield

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client



@pytest.fixture
def stub_city_catalogue(monkeypatch):
    """For tests that run services on a mocked database: city names resolve as the catalogue
    (migration 016) would, without a query. Real-database tests use the real catalogue."""
    from app.modules.locations.service import CatalogueCity, LocationService

    known = {
        "bengaluru": CatalogueCity(slug="bengaluru", name="Bengaluru", state="Karnataka", state_code="KA",
                                   state_kind="state", is_capital=True, tier=1, latitude=12.9716,
                                   longitude=77.5946, aliases=("Bangalore",)),
        "mumbai": CatalogueCity(slug="mumbai", name="Mumbai", state="Maharashtra", state_code="MH",
                                state_kind="state", is_capital=True, tier=1, latitude=19.076,
                                longitude=72.8777, aliases=("Bombay",)),
    }

    async def resolve(self, name):
        return known.get((name or "").strip().casefold())

    monkeypatch.setattr(LocationService, "resolve", resolve)
