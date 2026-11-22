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
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_TYPE"] = "local"  # never upload to hosted buckets from tests

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
