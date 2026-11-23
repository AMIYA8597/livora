"""
Phone verification by SMS one-time code (launch gap 4b).

Previously /auth/otp/verify accepted the fixed codes 1234/123456 for anyone, needed no login,
and verified nothing. These tests pin the real behaviour.
"""
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestException
from app.infrastructure.sms import (
    MemorySmsProvider,
    SmsConfigurationError,
    TwilioSmsProvider,
    build_sms_provider,
    set_sms_provider,
)
from app.modules.auth.models import PhoneVerification
from app.modules.auth.phone_verification import normalize_phone


@pytest.fixture
def sms():
    provider = MemorySmsProvider()
    set_sms_provider(provider)
    yield provider
    set_sms_provider(None)


def _phone() -> str:
    # Unique valid Indian mobile per test run.
    return "9" + f"{uuid4().int % 10**9:09d}"


async def _register(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": f"otp_{uuid4().hex[:10]}@example.in", "password": "Password123!",
        "full_name": "Otp Tester", "role": "seeker",
    })
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["user"]["id"], {"Authorization": f"Bearer {data['access_token']}"}


async def _send(client, headers, phone):
    return await client.post("/api/v1/auth/otp/send", json={"phone_number": phone}, headers=headers)


async def _verify(client, headers, phone, code):
    return await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone, "otp_code": code}, headers=headers)


# --- Normalisation -------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("9876543210", "+919876543210"),
    ("+91 98765 43210", "+919876543210"),
    ("09876543210", "+919876543210"),
    ("919876543210", "+919876543210"),
    ("0091-98765-43210", "+919876543210"),
    ("+14155550123", "+14155550123"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["12345", "5876543210", "+91 12345 67890", "abcdefghij", "+0123456789"])
def test_normalize_phone_rejects_invalid(raw):
    with pytest.raises(BadRequestException):
        normalize_phone(raw)


# --- Flow ----------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_endpoints_require_login(async_client: AsyncClient):
    assert (await _send(async_client, {}, "9876543210")).status_code == 401
    assert (await _verify(async_client, {}, "9876543210", "123456")).status_code == 401


@pytest.mark.asyncio
async def test_send_and_verify_marks_number_verified(async_client: AsyncClient, sms):
    user_id, headers = await _register(async_client)
    phone = _phone()
    sent = await _send(async_client, headers, phone)
    assert sent.status_code == 200, sent.text
    code = sent.json()["dev_code"]  # echoed only in development/test
    assert len(code) == 6 and code.isdigit()
    assert sms.outbox[-1].to == f"+91{phone}" and code in sms.outbox[-1].body

    ok = await _verify(async_client, headers, phone, code)
    assert ok.status_code == 200, ok.text
    me = (await async_client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["phone_verified"] is True and me["phone_number"] == f"+91{phone}"
    assert "phone_verified_at" not in me

    # Single use.
    assert (await _verify(async_client, headers, phone, code)).status_code == 400

    # Only a keyed hash is stored.
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(PhoneVerification).where(PhoneVerification.user_id == user_id))).scalars().first()
        assert row.code_hash != code and code not in row.code_hash and len(row.code_hash) == 64


@pytest.mark.asyncio
async def test_former_fixed_codes_do_not_work(async_client: AsyncClient, sms):
    _, headers = await _register(async_client)
    phone = _phone()
    code = (await _send(async_client, headers, phone)).json()["dev_code"]
    for fixed in ("123456", "000000"):
        if fixed != code:
            assert (await _verify(async_client, headers, phone, fixed)).status_code == 400
    # 4-digit codes are rejected outright.
    assert (await _verify(async_client, headers, phone, "1234")).status_code == 422


@pytest.mark.asyncio
async def test_attempts_are_limited_then_code_is_burned(async_client: AsyncClient, sms):
    _, headers = await _register(async_client)
    phone = _phone()
    code = (await _send(async_client, headers, phone)).json()["dev_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert (await _verify(async_client, headers, phone, wrong)).status_code == 400
    # Even the right code no longer works: brute force is capped at OTP_MAX_ATTEMPTS guesses.
    assert (await _verify(async_client, headers, phone, code)).status_code == 400


@pytest.mark.asyncio
async def test_expired_code_rejected(async_client: AsyncClient, sms):
    user_id, headers = await _register(async_client)
    phone = _phone()
    code = (await _send(async_client, headers, phone)).json()["dev_code"]
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE phone_verifications SET expires_at = now() - interval '1 second' WHERE user_id = :u"),
                        {"u": user_id})
        await s.commit()
    assert (await _verify(async_client, headers, phone, code)).status_code == 400


@pytest.mark.asyncio
async def test_code_is_bound_to_user_and_number(async_client: AsyncClient, sms):
    _, alice = await _register(async_client)
    _, bob = await _register(async_client)
    phone, other = _phone(), _phone()
    code = (await _send(async_client, alice, phone)).json()["dev_code"]
    assert (await _verify(async_client, bob, phone, code)).status_code == 400      # someone else's code
    assert (await _verify(async_client, alice, other, code)).status_code == 400    # different number
    assert (await _verify(async_client, alice, phone, code)).status_code == 200


@pytest.mark.asyncio
async def test_resend_cooldown(async_client: AsyncClient, sms):
    _, headers = await _register(async_client)
    phone = _phone()
    assert (await _send(async_client, headers, phone)).status_code == 200
    again = await _send(async_client, headers, phone)
    assert again.status_code == 429


@pytest.mark.asyncio
async def test_hourly_cap_per_number_across_accounts(async_client: AsyncClient, sms, monkeypatch):
    """Stops SMS-bombing one victim's number from many accounts."""
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(settings, "OTP_MAX_SENDS_PER_HOUR", 2)
    victim = _phone()
    for _ in range(2):
        _, headers = await _register(async_client)
        assert (await _send(async_client, headers, victim)).status_code == 200
    _, attacker = await _register(async_client)
    assert (await _send(async_client, attacker, victim)).status_code == 429


@pytest.mark.asyncio
async def test_new_code_supersedes_old(async_client: AsyncClient, sms, monkeypatch):
    monkeypatch.setattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 0)
    _, headers = await _register(async_client)
    phone = _phone()
    first = (await _send(async_client, headers, phone)).json()["dev_code"]
    second = (await _send(async_client, headers, phone)).json()["dev_code"]
    if first != second:
        assert (await _verify(async_client, headers, phone, first)).status_code == 400
    assert (await _verify(async_client, headers, phone, second)).status_code == 200


@pytest.mark.asyncio
async def test_number_verified_on_one_account_only(async_client: AsyncClient, sms):
    _, alice = await _register(async_client)
    _, bob = await _register(async_client)
    phone = _phone()
    code = (await _send(async_client, alice, phone)).json()["dev_code"]
    assert (await _verify(async_client, alice, phone, code)).status_code == 200
    assert (await _send(async_client, bob, phone)).status_code == 409


@pytest.mark.asyncio
async def test_changing_number_clears_verification(async_client: AsyncClient, sms):
    _, headers = await _register(async_client)
    phone = _phone()
    code = (await _send(async_client, headers, phone)).json()["dev_code"]
    assert (await _verify(async_client, headers, phone, code)).status_code == 200
    resp = await async_client.put("/api/v1/users/me", json={"phone_number": f"+91{_phone()}"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone_verified"] is False


@pytest.mark.asyncio
async def test_unconfigured_sms_returns_503_and_sends_nothing(async_client: AsyncClient, monkeypatch):
    set_sms_provider(None)
    monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")  # no credentials configured
    _, headers = await _register(async_client)
    resp = await _send(async_client, headers, _phone())
    set_sms_provider(None)
    assert resp.status_code == 503


# --- Providers -----------------------------------------------------------------------------

def test_memory_sms_refused_outside_dev(monkeypatch):
    monkeypatch.setattr(settings, "SMS_PROVIDER", "memory")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(SmsConfigurationError):
        build_sms_provider()


@pytest.mark.asyncio
async def test_twilio_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(201, json={"sid": "SM123"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TwilioSmsProvider("AC123", "tok", messaging_service_sid="MG456", client=client)
        assert await provider.send("+919876543210", "123456 is your code") == "SM123"
    assert seen["url"].endswith("/Accounts/AC123/Messages.json")
    assert "MessagingServiceSid=MG456" in seen["body"] and "To=%2B919876543210" in seen["body"]
    assert seen["auth"].startswith("Basic ")



def test_bad_sms_config_does_not_stop_startup(monkeypatch):
    from app.infrastructure.sms import init_sms_provider
    set_sms_provider(None)
    monkeypatch.setattr(settings, "SMS_PROVIDER", "twilio")  # no credentials
    init_sms_provider()  # logs an error, does not raise
    set_sms_provider(None)
