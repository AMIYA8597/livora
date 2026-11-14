import pytest
from uuid import uuid4
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()

@pytest.mark.asyncio
async def test_auth_registration_and_password_recovery(async_client: AsyncClient):
    test_email = f"lifecycle_{uuid4().hex[:8]}@example.in"
    # 1. Register a new user
    reg_payload = {
        "email": test_email,
        "password": "Password123!",
        "full_name": "Lifecycle Tester",
        "role": "seeker",
        "phone_number": "+919876543210",
    }
    reg_resp = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert "refresh_token" in reg_data
    assert reg_data["user"]["email"] == test_email

    # 2. Login
    login_resp = await async_client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "Password123!",
    })
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 3. Refresh token
    refresh_resp = await async_client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()

    # 4. Forgot password request
    forgot_resp = await async_client.post("/api/v1/auth/forgot-password", json={
        "email": test_email,
    })
    assert forgot_resp.status_code == 200
    forgot_data = forgot_resp.json()
    assert forgot_data["success"] is True
    assert "reset_token" in forgot_data
    reset_token = forgot_data["reset_token"]

    # 5. Reset password with new password
    reset_resp = await async_client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": "NewSecurePassword456!",
    })
    assert reset_resp.status_code == 200

    # 6. Verify old password no longer works
    old_login = await async_client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "Password123!",
    })
    assert old_login.status_code == 401

    # 7. Verify new password works
    new_login = await async_client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "NewSecurePassword456!",
    })
    assert new_login.status_code == 200

    # 8. Test storage file upload with authenticated token
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    files = {"file": ("test_avatar.jpg", b"\xff\xd8\xff\xe0test_avatar_bytes", "image/jpeg")}
    upload_resp = await async_client.post(
        "/api/v1/storage/upload",
        data={"bucket": "avatars"},
        files=files,
        headers=auth_headers,
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    assert upload_data["bucket"] == "avatars"
    assert "url" in upload_data

    # 9. Test storage signed URL for verification bucket
    doc_files = {"file": ("aadhaar.pdf", b"%PDF-1.4 test document content", "application/pdf")}
    doc_upload = await async_client.post(
        "/api/v1/storage/upload",
        data={"bucket": "verification"},
        files=doc_files,
        headers=auth_headers,
    )
    assert doc_upload.status_code == 201
    doc_path = doc_upload.json()["path"]

    signed_resp = await async_client.get(
        f"/api/v1/storage/signed-url?bucket=verification&path={doc_path}",
        headers=auth_headers,
    )
    assert signed_resp.status_code == 200
    assert "signed_url" in signed_resp.json()

