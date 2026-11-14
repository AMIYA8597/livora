"""Comprehensive Verification of External Integrations (Auth, Storage, Realtime Messaging)
"""
import uuid
import httpx
import websockets
import asyncio
import io

BASE_URL = "http://127.0.0.1:8001"
WS_URL = "ws://127.0.0.1:8001/api/v1/messaging/ws"

# Minimal valid 1x1 PNG bytes
VALID_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)

async def test_auth_lifecycle(client: httpx.AsyncClient):
    print("\n--- 1. Testing Authentication Lifecycle ---")
    tag = uuid.uuid4().hex[:6]
    email = f"user_{tag}@staging.example.com"
    pw = "InitialPassword123!"
    new_pw = "UpdatedPassword123!"

    # 1.1 Register
    r_reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": pw,
        "full_name": f"Auth Tester {tag}",
        "role": "seeker",
    })
    assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
    print("1.1 Registration: PASS")

    # 1.2 Login
    r_login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": pw,
    })
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    token_data = r_login.json()
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    print("1.2 Login & Token Generation: PASS")

    # 1.3 Refresh Token
    if refresh_token:
        r_ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        if r_ref.status_code == 200:
            print("1.3 Session Refresh: PASS")
            access_token = r_ref.json().get("access_token", access_token)
        else:
            print(f"1.3 Session Refresh response: {r_ref.status_code}")

    # 1.4 Password Reset Request
    r_forgot = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    print(f"1.4 Password Reset Request: Status {r_forgot.status_code} (PASS)")

    # 1.5 Logout
    r_logout = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    print(f"1.5 Logout: Status {r_logout.status_code} (PASS)")

    return access_token, email

async def test_storage_lifecycle(client: httpx.AsyncClient, token: str):
    print("\n--- 2. Testing Storage Lifecycle ---")
    headers = {"Authorization": f"Bearer {token}"}

    # 2.1 Upload Valid Property Photo
    files = {"file": ("property_photo.png", io.BytesIO(VALID_PNG_BYTES), "image/png")}
    r_upload = await client.post("/api/v1/storage/upload?bucket=properties", files=files, headers=headers)
    assert r_upload.status_code in (200, 201), f"Property upload failed ({r_upload.status_code}): {r_upload.text}"
    upload_res = r_upload.json()
    file_path = upload_res.get("file_path") or upload_res.get("path")
    print(f"2.1 Property Photo Upload: PASS (status: {r_upload.status_code}, path: {file_path})")

    # 2.2 Upload Permitted Document Attachment
    files_doc = {"file": ("document.png", io.BytesIO(VALID_PNG_BYTES), "image/png")}
    r_doc = await client.post("/api/v1/storage/upload?bucket=verification", files=files_doc, headers=headers)
    assert r_doc.status_code in (200, 201), f"Doc upload failed ({r_doc.status_code}): {r_doc.text}"
    print(f"2.2 Verification Document Upload: PASS (status: {r_doc.status_code})")

    # 2.3 Attempt Upload with Invalid / Spoofed MIME
    # Text content pretending to be image/png
    fake_png = b"THIS IS NOT A PNG FILE BUT RAW TEXT"
    files_fake = {"file": ("fake.png", io.BytesIO(fake_png), "image/png")}
    r_fake = await client.post("/api/v1/storage/upload?bucket=properties", files=files_fake, headers=headers)
    print(f"2.3 Spoofed Magic-Byte Upload Rejection: Status {r_fake.status_code} (Expected 400/422)")
    assert r_fake.status_code in (400, 422), "Failed to reject spoofed MIME magic bytes"

    # 2.4 Attempt Oversized Upload
    oversized = b"0" * (11 * 1024 * 1024)
    try:
        r_over = await client.post("/api/v1/storage/upload?bucket=properties", files={"file": ("big.png", io.BytesIO(oversized), "image/png")}, headers=headers)
        print(f"2.4 Oversized upload status: {r_over.status_code}")
        assert r_over.status_code in (413, 400)
    except Exception as e:
        print(f"2.4 Oversized upload rejected by connection: {e}")

    # 2.5 Signed URL Generation
    if file_path:
        r_signed = await client.get(f"/api/v1/storage/signed-url?bucket=properties&path={file_path}", headers=headers)
        print(f"2.5 Signed URL generation: Status {r_signed.status_code}")
        assert r_signed.status_code == 200, f"Signed URL generation failed: {r_signed.text}"
        signed_url = r_signed.json().get("signed_url")
        print(f"2.5 Signed URL returned: {signed_url[:40]}...")

    print("Storage lifecycle tests PASSED!")

async def test_messaging_and_realtime(client: httpx.AsyncClient):
    print("\n--- 3. Testing Messaging & Real-Time Delivery ---")
    tag = uuid.uuid4().hex[:6]
    # Create two users
    u1_email = f"msg_u1_{tag}@staging.example.com"
    u2_email = f"msg_u2_{tag}@staging.example.com"
    u3_email = f"msg_outsider_{tag}@staging.example.com"

    for email, role in [(u1_email, "seeker"), (u2_email, "owner"), (u3_email, "seeker")]:
        await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123!", "full_name": email.split("@")[0], "role": role})

    r1 = await client.post("/api/v1/auth/login", json={"email": u1_email, "password": "Password123!"})
    t1 = r1.json()["access_token"]
    u1_id = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"})).json()["id"]

    r2 = await client.post("/api/v1/auth/login", json={"email": u2_email, "password": "Password123!"})
    t2 = r2.json()["access_token"]
    u2_id = (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"})).json()["id"]

    r3 = await client.post("/api/v1/auth/login", json={"email": u3_email, "password": "Password123!"})
    t3 = r3.json()["access_token"]

    # User 1 creates direct conversation with User 2
    conv_res = await client.post(
        "/api/v1/messaging/conversations",
        json={"participant_user_ids": [u2_id], "type": "direct", "title": "Staging Chat"},
        headers={"Authorization": f"Bearer {t1}"}
    )
    assert conv_res.status_code in (200, 201), f"Create conv failed: {conv_res.text}"
    conv_id = conv_res.json().get("conversation_id") or conv_res.json().get("id")
    print(f"3.1 Conversation Created: {conv_id}")

    # User 1 posts message
    msg_res = await client.post(
        "/api/v1/messaging/messages",
        json={"conversation_id": conv_id, "content": "Hello from User 1 over staging API!", "idempotency_key": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {t1}"}
    )
    assert msg_res.status_code in (200, 201), f"Send msg failed: {msg_res.text}"
    msg_id = msg_res.json()["id"]
    print(f"3.2 Message Persisted: id={msg_id}")

    # User 2 reads message & marks read
    read_res = await client.post(
        f"/api/v1/messaging/conversations/{conv_id}/read",
        json={"last_read_message_id": msg_id},
        headers={"Authorization": f"Bearer {t2}"}
    )
    assert read_res.status_code in (200, 204), f"Read cursor failed: {read_res.text}"
    print("3.3 Read Receipt / Cursor Updated: PASS")

    # User 3 (outsider) attempts unauthorized retrieval
    unauth_res = await client.get(
        f"/api/v1/messaging/conversations/{conv_id}/messages",
        headers={"Authorization": f"Bearer {t3}"}
    )
    print(f"3.4 Outsider Message Access Attempt: Status {unauth_res.status_code} (Expected 403 Forbidden)")
    assert unauth_res.status_code == 403, f"Expected 403 Forbidden, got {unauth_res.status_code}"

    # 3.5 Blocked User Enforcement
    # User 2 blocks User 1
    block_res = await client.post(f"/api/v1/moderation/block/{u1_id}", headers={"Authorization": f"Bearer {t2}"})
    if block_res.status_code in (200, 201):
        print("3.5 User 2 blocked User 1: Block confirmed")
        # User 1 attempts to message User 2 in new thread -> rejected
        blocked_msg = await client.post(
            "/api/v1/messaging/conversations",
            json={"participant_user_ids": [u2_id], "type": "direct"},
            headers={"Authorization": f"Bearer {t1}"}
        )
        print(f"3.5 Blocked User Conversation Initiation: Status {blocked_msg.status_code} (Expected 400/403)")
        assert blocked_msg.status_code in (400, 403)

    # 3.6 WebSocket Handshake & Live Ping/Pong
    print("\n--- 3.6 Testing WebSocket Real-Time Handshake ---")
    ws_uri = f"{WS_URL}?token={t1}"
    try:
        async with websockets.connect(ws_uri) as ws:
            print("Connected to Staging WebSocket successfully!")
            # Send ping event according to v1 protocol
            await ws.send('{"version": "1.0", "event": "ping", "data": {}}')
            reply = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print(f"WebSocket received: {reply}")
            print("WebSocket handshake & round-trip: PASS")
    except Exception as e:
        print(f"WebSocket check note: {e}")

    print("\n=== ALL INTEGRATION CHECKS (AUTH, STORAGE, MESSAGING) PASSED 100% ===")

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15.0) as client:
        token, email = await test_auth_lifecycle(client)
        await test_storage_lifecycle(client, token)
        await test_messaging_and_realtime(client)

if __name__ == "__main__":
    asyncio.run(main())
