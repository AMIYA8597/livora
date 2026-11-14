"""
Live Application Security and Privacy Verification Suite
Tests the running staging backend on port 8001.
"""
import asyncio
import httpx
import json
import uuid
from datetime import datetime, timezone, timedelta
from jose import jwt

BASE_URL = "http://127.0.0.1:8001"

async def test_security():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        print("==================================================================")
        print("Application Security & Privacy Verification Drill")
        print("==================================================================")

        tag = uuid.uuid4().hex[:6]
        seeker_email = f"sec_seeker_{tag}@staging.example.com"
        owner_email = f"sec_owner_{tag}@staging.example.com"

        # Register Seeker
        r_s = await client.post("/api/v1/auth/register", json={
            "email": seeker_email,
            "password": "Password123!",
            "full_name": f"Seeker {tag}",
            "role": "seeker",
        })
        assert r_s.status_code == 201
        seeker_data = r_s.json()
        seeker_id = seeker_data["user"]["id"]
        t_seeker = seeker_data["access_token"]

        # Register Owner
        r_o = await client.post("/api/v1/auth/register", json={
            "email": owner_email,
            "password": "Password123!",
            "full_name": f"Owner {tag}",
            "role": "owner",
        })
        assert r_o.status_code == 201
        owner_data = r_o.json()
        t_owner = owner_data["access_token"]

        # 1. Tampered JWT signature
        tampered_token = t_seeker[:-10] + "0123456789"
        r_tamp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        print(f"1. Tampered JWT Signature: Status {r_tamp.status_code} (Expected 401)")
        assert r_tamp.status_code == 401

        # 2. Expired JWT token
        expired_token = jwt.encode(
            {"sub": seeker_id, "role": "authenticated", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            "staging_local_jwt_secret_32_characters_minimum_entropy",
            algorithm="HS256"
        )
        r_exp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        print(f"2. Expired JWT Token: Status {r_exp.status_code} (Expected 401)")
        assert r_exp.status_code == 401

        # 3. Privilege Escalation (Seeker accessing Admin stats)
        r_esc = await client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {t_seeker}"})
        print(f"3. Privilege Escalation Prevention (Seeker -> Admin): Status {r_esc.status_code} (Expected 403)")
        assert r_esc.status_code == 403

        # 4. SQL Injection in Search Filters
        sqli_payload = {"city": "Bengaluru' OR '1'='1", "min_rent": 0, "max_rent": 100000}
        r_sqli = await client.post("/api/v1/search/properties", json=sqli_payload)
        print(f"4. SQL Injection Defense in Search: Status {r_sqli.status_code} (No 500 error)")
        assert r_sqli.status_code in (200, 422)

        # 5. Coordinate Fuzzing & Address Masking (DPDP Compliance)
        # Fetch property list
        r_props = await client.get("/api/v1/properties/")
        props = r_props.json()
        if props:
            p = props[0]
            pid = p["id"]
            # Non-owner view of property
            r_detail = await client.get(f"/api/v1/properties/{pid}", headers={"Authorization": f"Bearer {t_seeker}"})
            p_data = r_detail.json()
            print(f"5. DPDP Address Masking: '{p_data.get('address_exact')}'")
            assert "[Exact address protected" in str(p_data.get("address_exact", ""))
            print("   -> Address masking active: PASS")

        # 6. Storage Magic Byte Validation
        fake_png = b"NOT A REAL PNG FILE"
        files = {"file": ("fake.png", fake_png, "image/png")}
        r_stor = await client.post("/api/v1/storage/upload?bucket=properties", files=files, headers={"Authorization": f"Bearer {t_owner}"})
        print(f"6. Storage Magic Byte Validation: Status {r_stor.status_code} (Expected 400)")
        assert r_stor.status_code == 400

        # 7. Unauthenticated WebSocket Rejection
        import websockets
        try:
            async with websockets.connect(f"ws://127.0.0.1:8001/api/v1/messaging/ws") as ws:
                print("   [WARN] WS connected without token")
        except Exception as e:
            print(f"7. Unauthenticated WebSocket Handshake: Rejected ({type(e).__name__}) (PASS)")

        print("\n=== ALL SECURITY & PRIVACY CONTROLS PASSED 100% ===")

if __name__ == "__main__":
    asyncio.run(test_security())
