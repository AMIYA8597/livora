import pytest
from uuid import uuid4
from httpx import AsyncClient
from app.core.security import create_access_token, decode_token

@pytest.mark.asyncio
async def test_trace_headers_and_health(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") is not None
    assert response.headers.get("X-Process-Time-Ms") is not None
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"

@pytest.mark.asyncio
async def test_readiness_probe(async_client: AsyncClient):
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"

def test_supabase_token_claims():
    user_id = str(uuid4())
    roles = ["seeker", "tenant"]
    email = "test.seeker@example.in"

    token = create_access_token(subject=user_id, roles=roles, email=email)
    claims = decode_token(token)

    assert claims["sub"] == user_id
    assert claims["email"] == email
    assert claims["role"] == "authenticated"
    assert "seeker" in claims["app_metadata"]["roles"]
    assert "tenant" in claims["app_metadata"]["roles"]
