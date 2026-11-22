"""
Storage access rules (launch gap 2h): bucket registry, generic-endpoint restrictions,
chat-attachment authorisation and listing-photo upload rights.
"""
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.infrastructure.storage_buckets import bucket_registry
from tests.image_samples import make_image

PDF = b"%PDF-1.4\n%probe\n" + b"0" * 64


async def _register(client: AsyncClient, role: str = "seeker"):
    email = f"st_{uuid4().hex[:10]}@example.in"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": f"Storage {role}", "role": role,
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["user"]["id"], {"Authorization": f"Bearer {data['access_token']}"}


# --- Registry invariants -------------------------------------------------------------------

def test_registry_marks_sensitive_buckets_private_and_limited():
    reg = bucket_registry()
    assert reg["verification"].public is False and reg["chat_attachments"].public is False
    assert reg["properties"].public is True and reg["avatars"].public is True
    for spec in reg.values():
        assert spec.max_bytes <= 15 * 1024 * 1024 and spec.mime_types
    # Chat files are reachable only through the conversation endpoints.
    assert reg["chat_attachments"].generic_upload is False and reg["chat_attachments"].generic_signed_url is False


def test_physical_names_come_from_settings():
    assert bucket_registry()["chat_attachments"].physical == settings.STORAGE_BUCKET_CHAT_ATTACHMENTS == "chat-attachments"


# --- Generic endpoints ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generic_signed_url_cannot_reach_chat_attachments(async_client: AsyncClient):
    """Previously any signed-in user could sign any chat attachment path (IDOR)."""
    _, headers = await _register(async_client)
    resp = await async_client.get(
        "/api/v1/storage/signed-url",
        params={"bucket": "chat_attachments", "path": f"{uuid4()}/{uuid4()}.pdf"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generic_signed_url_refuses_public_buckets(async_client: AsyncClient):
    _, headers = await _register(async_client)
    resp = await async_client.get(
        "/api/v1/storage/signed-url", params={"bucket": "avatars", "path": "x/y.jpg"}, headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generic_upload_cannot_target_chat_attachments(async_client: AsyncClient):
    _, headers = await _register(async_client)
    resp = await async_client.post(
        "/api/v1/storage/upload", data={"bucket": "chat_attachments"},
        files={"file": ("a.pdf", PDF, "application/pdf")}, headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_verification_documents_are_owner_only(async_client: AsyncClient):
    owner_id, owner_headers = await _register(async_client)
    _, other_headers = await _register(async_client)
    up = await async_client.post(
        "/api/v1/storage/upload", data={"bucket": "verification"},
        files={"file": ("id.pdf", PDF, "application/pdf")}, headers=owner_headers,
    )
    assert up.status_code == 201, up.text
    path = up.json()["path"]
    assert path.startswith(f"{owner_id}/") and up.json()["is_private"] is True

    mine = await async_client.get("/api/v1/storage/signed-url", params={"bucket": "verification", "path": path}, headers=owner_headers)
    theirs = await async_client.get("/api/v1/storage/signed-url", params={"bucket": "verification", "path": path}, headers=other_headers)
    assert mine.status_code == 200 and theirs.status_code == 403


# --- Listing photos ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seekers_cannot_use_public_property_bucket_as_image_hosting(async_client: AsyncClient):
    _, headers = await _register(async_client, role="seeker")
    resp = await async_client.post(
        "/api/v1/storage/upload", data={"bucket": "properties"},
        files={"file": ("p.jpg", make_image("JPEG"), "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_owners_can_upload_listing_photos_before_the_listing_exists(async_client: AsyncClient):
    _, headers = await _register(async_client, role="owner")
    resp = await async_client.post(
        "/api/v1/storage/upload", data={"bucket": "properties"},
        files={"file": ("p.jpg", make_image("JPEG"), "image/jpeg")}, headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_private"] is False


# --- Chat attachments through the conversation endpoints -----------------------------------

@pytest.mark.asyncio
async def test_chat_attachments_are_participant_only(async_client: AsyncClient):
    alice_id, alice = await _register(async_client)
    bob_id, bob = await _register(async_client)
    _, mallory = await _register(async_client)

    conv = await async_client.post(
        "/api/v1/messaging/conversations", json={"participant_user_ids": [bob_id], "type": "direct"}, headers=alice,
    )
    assert conv.status_code == 201, conv.text
    conversation_id = conv.json()["conversation_id"]

    up = await async_client.post(
        f"/api/v1/messaging/conversations/{conversation_id}/attachments",
        files={"file": ("lease.pdf", PDF, "application/pdf")}, headers=alice,
    )
    assert up.status_code == 201, up.text
    attachment = up.json()

    # Stored in the physical bucket, not the logical name.
    from app.infrastructure.storage import get_storage
    base_dir = getattr(get_storage(), "base_dir", None)
    if base_dir is not None:
        assert (Path(base_dir) / settings.STORAGE_BUCKET_CHAT_ATTACHMENTS / attachment["file_path"]).exists()

    ok = await async_client.get(f"/api/v1/messaging/attachments/{attachment['id']}/download", headers=bob)
    denied = await async_client.get(f"/api/v1/messaging/attachments/{attachment['id']}/download", headers=mallory)
    assert ok.status_code == 200 and "signed_url" in ok.json()
    assert denied.status_code == 403

    # The generic endpoint does not sign it either, even with the exact path.
    leak = await async_client.get(
        "/api/v1/storage/signed-url", params={"bucket": "chat_attachments", "path": attachment["file_path"]}, headers=mallory,
    )
    assert leak.status_code == 403


# --- Storage RLS policy guard (scripts/check_storage_policies.py) ---------------------------

@pytest.mark.asyncio
async def test_storage_policy_guard_flags_public_role_policies():
    import importlib.util
    from sqlalchemy import text
    from tests.db_owner import owner_session_factory

    script = Path(__file__).resolve().parents[3] / "scripts" / "check_storage_policies.py"
    spec = importlib.util.spec_from_file_location("check_storage_policies", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async with owner_session_factory()() as session:
        try:
            # Recreate Supabase's storage schema shape inside a transaction.
            await session.execute(text("CREATE SCHEMA IF NOT EXISTS storage"))
            await session.execute(text("CREATE TABLE IF NOT EXISTS storage.objects (id uuid, bucket_id text)"))
            await session.execute(text("ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY"))
            clean = (await session.execute(text(module.QUERY))).all()
            await session.execute(text(
                "CREATE POLICY anyone_can_upload ON storage.objects FOR INSERT TO public WITH CHECK (true)"))
            flagged = (await session.execute(text(module.QUERY))).all()
        finally:
            await session.rollback()

    assert clean == []
    assert [r.policyname for r in flagged] == ["anyone_can_upload"]
