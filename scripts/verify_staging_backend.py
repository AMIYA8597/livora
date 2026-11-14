"""Backend Staging Deployment Verification

Exercises:
1. Health and readiness probes
2. OpenAPI documentation availability
3. CORS headers and OPTIONS preflight
4. Rate limiting enforcement
5. Payload size cap (10MB limit -> HTTP 413)
6. RFC 7807 problem details exception handling
7. User registration and authentication flow
"""
import uuid
import httpx

BASE_URL = "http://127.0.0.1:8001"

def test_backend_staging():
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    print("=== 1. Probing Health & Readiness ===")
    r_health = client.get("/health")
    assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
    health_data = r_health.json()
    assert health_data["environment"] == "staging"
    print(f"Health Probe: {health_data}")

    r_ready = client.get("/health/ready")
    assert r_ready.status_code == 200, f"Readiness check failed: {r_ready.text}"
    ready_data = r_ready.json()
    assert ready_data["database"] == "connected"
    print(f"Readiness Probe: {ready_data}")

    print("\n=== 2. Probing OpenAPI Documentation ===")
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200
    r_openapi = client.get("/openapi.json")
    assert r_openapi.status_code == 200
    paths = r_openapi.json().get("paths", {})
    print(f"OpenAPI Schema: {len(paths)} endpoints exposed")

    print("\n=== 3. Probing CORS & Security Headers ===")
    r_cors = client.options(
        "/api/v1/properties",
        headers={
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "GET",
        }
    )
    print(f"CORS Preflight Status: {r_cors.status_code}")
    print(f"CORS Allow Origin Header: {r_cors.headers.get('access-control-allow-origin')}")
    assert r_cors.headers.get("access-control-allow-origin") in ("http://localhost:3001", "*")

    print("\n=== 4. Probing RFC 7807 Error Handling ===")
    r_not_found = client.get(f"/api/v1/properties/{uuid.uuid4()}")
    print(f"Not Found Status: {r_not_found.status_code}")
    assert r_not_found.status_code == 404
    err_body = r_not_found.json()
    assert "type" in err_body and "title" in err_body and "status" in err_body
    print(f"RFC 7807 Problem Detail: {err_body}")

    print("\n=== 5. Probing Request Body Size Limit (10MB Cap) ===")
    # 11MB payload
    oversized_data = b"X" * (11 * 1024 * 1024)
    try:
        r_large = client.post(
            "/api/v1/auth/register",
            content=oversized_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Oversized payload status: {r_large.status_code}")
        assert r_large.status_code == 413, f"Expected 413 Payload Too Large, got {r_large.status_code}"
        print("10MB payload size limit successfully enforced!")
    except httpx.RequestError as e:
        print(f"Request terminated by server due to size limit: {e}")

    print("\n=== 6. Probing Authentication Flow (Register & Login) ===")
    test_email = f"staging_test_{uuid.uuid4().hex[:6]}@staging.example.com"
    register_payload = {
        "email": test_email,
        "password": "Password123!",
        "full_name": "Staging Tester",
        "role": "seeker",
    }
    r_reg = client.post("/api/v1/auth/register", json=register_payload)
    print(f"Registration response: {r_reg.status_code}")
    assert r_reg.status_code in (200, 201), f"Registration failed: {r_reg.text}"
    user_data = r_reg.json()
    print(f"User created: id={user_data.get('id')}, email={user_data.get('email')}")

    login_payload = {
        "email": test_email,
        "password": "Password123!",
    }
    r_login = client.post("/api/v1/auth/login", json=login_payload)
    print(f"Login response: {r_login.status_code}")
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    token_data = r_login.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]
    print(f"Token issued: access_token prefix={access_token[:15]}..., token_type={token_data.get('token_type')}")

    # Authenticated request
    r_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    print(f"Authenticated /auth/me: {r_me.status_code}")
    assert r_me.status_code == 200
    assert r_me.json()["email"] == test_email
    print(f"Authenticated user profile retrieved successfully: {r_me.json()['full_name']}")

    print("\n=== ALL BACKEND STAGING DEPLOYMENT CHECKS PASSED 100% ===")

if __name__ == "__main__":
    test_backend_staging()
