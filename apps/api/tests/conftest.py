import sys
from pathlib import Path

# Add apps/api to sys.path so 'app' can be resolved regardless of execution root
api_root = str(Path(__file__).resolve().parent.parent)
if api_root not in sys.path:
    sys.path.insert(0, api_root)

import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from app.main import app

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
