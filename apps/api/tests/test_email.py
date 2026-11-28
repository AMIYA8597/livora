"""
Transactional email: templates, provider selection/retries, fail-safe sending,
password-reset delivery and single-use tokens, and domain-event notifications.
"""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.infrastructure.email import (
    EmailConfigurationError,
    EmailDeliveryError,
    MemoryEmailProvider,
    send_templated_email,
    set_email_provider,
)
from app.infrastructure.email.providers import ResendEmailProvider, OutgoingEmail, build_email_provider
from app.infrastructure.email.templates import render


@pytest.fixture
def outbox():
    provider = MemoryEmailProvider()
    set_email_provider(provider)
    yield provider.outbox
    set_email_provider(None)


# --- Templates ---------------------------------------------------------------------------

def test_templates_escape_user_controlled_values():
    rendered = render("application_received", {
        "name": "Owner",
        "applicant_name": '<script>alert(1)</script><a href="https://evil.example">x</a>',
        "property_title": "Flat & <b>Co</b>",
        "proposed_rent": 25000,
        "move_in_target": "2026-12-01",
        "dashboard_url": "http://localhost:3000/owner/dashboard",
    })
    assert "<script>" not in rendered.html
    assert 'href="https://evil.example"' not in rendered.html
    assert "&lt;script&gt;" in rendered.html
    assert "Flat &amp; &lt;b&gt;Co&lt;/b&gt;" in rendered.html
    # Plain-text part and subject keep the readable value.
    assert "Flat & <b>Co</b>" in rendered.subject


def test_subject_cannot_carry_header_injection():
    rendered = render("appointment_requested", {
        "name": "Host", "applicant_name": "A", "property_title": "Nice flat\r\nBcc: victim@example.com",
        "scheduled_for": "01 Dec 2026", "dashboard_url": "http://x",
    })
    assert "\n" not in rendered.subject and "\r" not in rendered.subject


def test_unknown_template_rejected():
    with pytest.raises(KeyError):
        render("nope", {})


# --- Provider selection --------------------------------------------------------------------

def test_memory_provider_refused_outside_dev_and_test(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "memory")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(EmailConfigurationError):
        build_email_provider()


def test_resend_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "EMAIL_API_KEY", "")
    with pytest.raises(EmailConfigurationError):
        build_email_provider()


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "carrier-pigeon")
    with pytest.raises(EmailConfigurationError):
        build_email_provider()


# --- Resend HTTP behaviour -----------------------------------------------------------------

def _message():
    return OutgoingEmail(to="a@example.com", subject="s", html="<p>h</p>", text="t", idempotency_key="key-1")


@pytest.mark.asyncio
async def test_resend_retries_transient_errors_with_same_idempotency_key(monkeypatch):
    monkeypatch.setattr("app.infrastructure.email.providers.asyncio.sleep", _no_sleep)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Idempotency-Key"))
        if len(seen) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"id": "msg_123"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendEmailProvider("re_test", "Flatmate <n@flatmate.test>", client=client)
        assert await provider.send(_message()) == "msg_123"
    assert seen == ["key-1", "key-1", "key-1"]


@pytest.mark.asyncio
async def test_resend_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr("app.infrastructure.email.providers.asyncio.sleep", _no_sleep)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(422, json={"message": "invalid"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ResendEmailProvider("re_test", "n@flatmate.test", client=client)
        with pytest.raises(EmailDeliveryError):
            await provider.send(_message())
    assert len(calls) == 1


async def _no_sleep(_seconds):
    return None


@pytest.mark.asyncio
async def test_send_templated_email_never_raises():
    class Broken(MemoryEmailProvider):
        async def send(self, message):
            raise EmailDeliveryError("down")

    set_email_provider(Broken())
    try:
        assert await send_templated_email("a@example.com", "password_changed", {"name": "A"}) is False
    finally:
        set_email_provider(None)


# --- Password reset over the API -----------------------------------------------------------

async def _register(client: AsyncClient, role: str = "seeker"):
    email = f"mail_{uuid4().hex[:10]}@example.in"
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Password123!", "full_name": f"Mail {role.title()}", "role": role,
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return email, data["user"]["id"], data["access_token"]


@pytest.mark.asyncio
async def test_forgot_password_emails_a_reset_link(async_client: AsyncClient, outbox):
    email, _, _ = await _register(async_client)
    resp = await async_client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    token = resp.json()["reset_token"]  # echoed only because ENVIRONMENT=test

    sent = [m for m in outbox if m.to == email]
    assert len(sent) == 1
    assert sent[0].tags == {"template": "password_reset"}
    assert f"{settings.WEB_BASE_URL}/reset-password?token={token}" in sent[0].text
    assert sent[0].idempotency_key


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_sends_nothing_and_looks_identical(async_client: AsyncClient, outbox):
    known, _, _ = await _register(async_client)
    known_resp = await async_client.post("/api/v1/auth/forgot-password", json={"email": known})
    unknown_resp = await async_client.post("/api/v1/auth/forgot-password", json={"email": f"ghost_{uuid4().hex}@example.in"})
    assert unknown_resp.status_code == known_resp.status_code == 200
    assert unknown_resp.json()["message"] == known_resp.json()["message"]
    assert all(m.to == known for m in outbox)


@pytest.mark.asyncio
async def test_reset_token_not_exposed_outside_dev_and_test_even_with_debug(async_client: AsyncClient, outbox, monkeypatch):
    email, _, _ = await _register(async_client)
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "DEBUG", True)
    resp = await async_client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "reset_token" not in resp.json()
    assert any(m.to == email for m in outbox)  # still delivered by email


@pytest.mark.asyncio
async def test_reset_token_is_single_use_and_revoked_by_password_change(async_client: AsyncClient, outbox):
    email, _, _ = await _register(async_client)
    first = (await async_client.post("/api/v1/auth/forgot-password", json={"email": email})).json()["reset_token"]
    second = (await async_client.post("/api/v1/auth/forgot-password", json={"email": email})).json()["reset_token"]

    ok = await async_client.post("/api/v1/auth/reset-password", json={"token": first, "new_password": "BrandNew456!"})
    assert ok.status_code == 200
    assert any(m.to == email and m.tags["template"] == "password_changed" for m in outbox)

    replay = await async_client.post("/api/v1/auth/reset-password", json={"token": first, "new_password": "Attacker789!"})
    assert replay.status_code == 400
    sibling = await async_client.post("/api/v1/auth/reset-password", json={"token": second, "new_password": "Attacker789!"})
    assert sibling.status_code == 400

    login = await async_client.post("/api/v1/auth/login", json={"email": email, "password": "BrandNew456!"})
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_garbage_reset_token_rejected(async_client: AsyncClient):
    resp = await async_client.post("/api/v1/auth/reset-password", json={"token": "not-a-jwt", "new_password": "Whatever123!"})
    assert resp.status_code == 400


# --- Domain-event notifications ------------------------------------------------------------

@pytest.fixture
async def owner_listing(async_client: AsyncClient):
    from geoalchemy2.elements import WKTElement
    from sqlalchemy import delete
    from app.core.database import AsyncSessionLocal
    from app.modules.properties.models import Property
    from app.modules.users.models import User

    owner_email, owner_id, owner_token = await _register(async_client, role="owner")
    prop_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(Property(
            id=prop_id, owner_id=owner_id, title="Sunny <2BHK> & balcony", description="test",
            location=WKTElement("POINT(77.6245 12.9352)", srid=4326),
            address_display="Koramangala", address_exact="1 Test Street", city="Bengaluru", postal_code="560034",
            monthly_rent=Decimal("30000.00"), available_from=date.today(),
        ))
        await session.commit()
    yield {"email": owner_email, "id": owner_id, "token": owner_token, "property_id": str(prop_id)}
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == owner_id))
        await session.commit()


@pytest.mark.asyncio
async def test_application_lifecycle_notifies_owner_then_applicant(async_client: AsyncClient, outbox, owner_listing):
    applicant_email, applicant_id, applicant_token = await _register(async_client)
    resp = await async_client.post(
        "/api/v1/applications/",
        json={"property_id": owner_listing["property_id"], "introduction": "Hi", "proposed_rent": 29000, "move_in_target": str(date.today() + timedelta(days=18))},
        headers={"Authorization": f"Bearer {applicant_token}"},
    )
    assert resp.status_code == 201, resp.text
    application_id = resp.json()["id"]

    # The applicant's list says which listing each application is for, in one statement.
    mine = await async_client.get("/api/v1/applications/me", headers={"Authorization": f"Bearer {applicant_token}"})
    assert mine.status_code == 200
    assert [(a["id"], a["property_title"], a["property_city"]) for a in mine.json()] == [
        (application_id, "Sunny <2BHK> & balcony", "Bengaluru")
    ]
    assert int(mine.headers["X-DB-Queries"]) == 2  # the signed-in user, then the list

    to_owner = [m for m in outbox if m.to == owner_listing["email"]]
    assert [m.tags["template"] for m in to_owner] == ["application_received"]
    assert "Sunny &lt;2BHK&gt; &amp; balcony" in to_owner[0].html
    assert "Mail Seeker" in to_owner[0].text

    resp = await async_client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"status": "accepted"},
        headers={"Authorization": f"Bearer {owner_listing['token']}"},
    )
    assert resp.status_code == 200, resp.text
    to_applicant = [m for m in outbox if m.to == applicant_email]
    assert [m.tags["template"] for m in to_applicant] == ["application_status"]
    assert "was accepted" in to_applicant[0].subject

    from app.core.database import AsyncSessionLocal
    from sqlalchemy import delete
    from app.modules.users.models import User
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == applicant_id))
        await session.commit()


@pytest.mark.asyncio
async def test_appointment_request_notifies_host(async_client: AsyncClient, outbox, owner_listing):
    from datetime import datetime, timedelta, timezone
    _, applicant_id, applicant_token = await _register(async_client)
    when = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
    resp = await async_client.post(
        "/api/v1/appointments/",
        json={"property_id": owner_listing["property_id"], "host_id": owner_listing["id"],
              "scheduled_at": when.isoformat(), "appointment_type": "physical_visit"},
        headers={"Authorization": f"Bearer {applicant_token}"},
    )
    assert resp.status_code == 201, resp.text
    to_host = [m for m in outbox if m.to == owner_listing["email"]]
    assert [m.tags["template"] for m in to_host] == ["appointment_requested"]
    assert when.strftime("%d %b %Y") in to_host[0].text

    from app.core.database import AsyncSessionLocal
    from sqlalchemy import delete
    from app.modules.users.models import User
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.id == applicant_id))
        await session.commit()
