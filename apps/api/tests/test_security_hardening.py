import pytest
from httpx import AsyncClient, ASGITransport
from starlette.datastructures import Headers

from app.main import app
from app.core.exceptions import RateLimitException
from app.core.rate_limit import RateLimiter, SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_security_headers_present():
    """Verify production security headers are attached to responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
        assert "X-Request-ID" in response.headers
        assert "X-Process-Time-Ms" in response.headers


@pytest.mark.asyncio
async def test_payload_size_enforcement_413():
    """Verify middleware rejects oversized payloads with HTTP 413."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send fake 15MB content-length header
        response = await client.post(
            "/api/v1/search/properties",
            headers={"Content-Length": str(15 * 1024 * 1024)},
            content=b"oversized dummy",
        )
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        data = response.json()
        assert data["title"] == "Payload Too Large"
        assert data["status"] == 413
        assert "10485760" in data["detail"]


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window():
    """Verify sliding window algorithm tracks quota and blocks on limit."""
    limiter = SlidingWindowRateLimiter()
    key = "test-client-ip-127.0.0.1"

    # Allow 3 requests within 60s
    max_reqs = 3
    window = 60

    # 1st request
    allowed, remaining, _ = await limiter.is_allowed(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is True
    assert remaining == 2

    # 2nd request
    allowed, remaining, _ = await limiter.is_allowed(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is True
    assert remaining == 1

    # 3rd request
    allowed, remaining, _ = await limiter.is_allowed(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is True
    assert remaining == 0

    # 4th request -> blocked
    allowed, remaining, reset_sec = await limiter.is_allowed(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is False
    assert remaining == 0
    assert reset_sec > 0

    # Reset
    await limiter.reset(key)
    allowed, remaining, _ = await limiter.is_allowed(key, max_requests=max_reqs, window_seconds=window)
    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_dependency_blocks():
    """Verify FastAPI dependency raises RateLimitException on quota breach."""
    from fastapi import Request, Response

    rate_limiter = RateLimiter(max_requests=2, window_seconds=60, key_prefix="test_dep")

    # Mock request and response
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": Headers({"client-ip": "10.0.0.1"}).raw,
        "client": ("10.0.0.1", 12345),
    }
    req = Request(scope)
    res = Response()

    # Request 1: OK
    await rate_limiter(req, res)
    assert res.headers["X-RateLimit-Limit"] == "2"
    assert res.headers["X-RateLimit-Remaining"] == "1"

    # Request 2: OK
    await rate_limiter(req, res)
    assert res.headers["X-RateLimit-Remaining"] == "0"

    # Request 3: Blocked with RateLimitException
    with pytest.raises(RateLimitException) as exc_info:
        await rate_limiter(req, res)

    assert exc_info.value.status_code == 429
    assert res.headers["Retry-After"] is not None


@pytest.mark.asyncio
async def test_sql_injection_defense():
    """Verify that SQL injection strings in search queries are safely handled."""
    from app.infrastructure.external_services.semantic_search import KeywordFallbackSearchProvider
    from uuid import uuid4

    provider = KeywordFallbackSearchProvider()
    items = [
        {
            "id": uuid4(),
            "title": "2BHK Indiranagar 100ft road",
            "description": "Lovely flat with balcony",
            "locality": "Indiranagar",
        }
    ]

    malicious_inputs = [
        "' OR '1'='1' --",
        "admin'--",
        "'; DROP TABLE users; --",
        "1; SELECT * FROM profiles WHERE 'a'='a",
        "<script>alert('xss')</script>",
    ]

    for bad_input in malicious_inputs:
        # Must execute cleanly without unhandled exception or SQL syntax error
        results = await provider.search(bad_input, items)
        assert isinstance(results, list)
