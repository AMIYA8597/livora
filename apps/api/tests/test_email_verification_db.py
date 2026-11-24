"""
Work and college email verification against a real database: domain rules, code delivery,
wrong/expired/exhausted codes, one address per account, replacing a work email, the trust
status, and that ID-document checks are switched off.
"""
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestException
from app.core.security import create_access_token
from app.infrastructure.email import MemoryEmailProvider, set_email_provider
from app.modules.users.models import User
from app.modules.verification.domains import STUDENT_EMAIL, WORK_EMAIL, check_domain, normalize_email
from app.modules.verification.models import Verification

API = settings.API_V1_PREFIX


def _auth(user_id) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=['seeker'])}"}


@pytest.fixture
def outbox():
    provider = MemoryEmailProvider()
    set_email_provider(provider)
    yield provider.outbox
    set_email_provider(None)


@pytest.fixture
async def people():
    ids = SimpleNamespace(a=uuid4(), b=uuid4(), tag=uuid4().hex[:8])
    async with AsyncSessionLocal() as s:
        for key in ("a", "b"):
            s.add(User(id=getattr(ids, key), email=f"ver-{key}-{ids.tag}@example.com", hashed_password="x",
                       full_name=f"Person {key.upper()}", role="seeker"))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        await s.execute(delete(User).where(User.id.in_([ids.a, ids.b])))
        await s.commit()


async def _skip_cooldown(user_id):
    """Pretend earlier codes were sent long ago, so the resend cooldown and hourly cap don't apply."""
    async with AsyncSessionLocal() as s:
        await s.execute(update(Verification).where(Verification.user_id == user_id)
                        .values(created_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        await s.commit()


def _code_from(message) -> str:
    return re.search(r"\b(\d{6})\b", message.text).group(1)


async def _send(client, user_id, email, kind=WORK_EMAIL):
    return await client.post(f"{API}/verification/email/send", json={"verification_type": kind, "email": email},
                             headers=_auth(user_id))


async def _confirm(client, user_id, code):
    return await client.post(f"{API}/verification/email/confirm", json={"code": code}, headers=_auth(user_id))


@pytest.mark.parametrize("email,kind,ok", [
    ("Asha@Infosys.com", WORK_EMAIL, True),
    ("asha@gmail.com", WORK_EMAIL, False),
    ("asha@mail.yahoo.com", WORK_EMAIL, False),
    ("asha@outlook.in", WORK_EMAIL, False),
    ("asha@mailinator.com", WORK_EMAIL, False),
    ("asha@iitb.ac.in", STUDENT_EMAIL, True),
    ("asha@cse.iitb.ac.in", STUDENT_EMAIL, True),
    ("asha@stanford.edu", STUDENT_EMAIL, True),
    ("asha@du.edu.in", STUDENT_EMAIL, True),
    ("asha@infosys.com", STUDENT_EMAIL, False),
    ("asha@gmail.com", STUDENT_EMAIL, False),
    ("asha@iitb.ac.in", WORK_EMAIL, True),  # university staff
])
def test_domain_rules(email, kind, ok):
    address, domain = normalize_email(email)
    assert address == email.lower() and domain == email.lower().split("@")[1]
    if ok:
        check_domain(domain, kind)
    else:
        with pytest.raises(BadRequestException):
            check_domain(domain, kind)


def test_malformed_address_is_refused():
    for bad in ("", "not-an-email", "a@", "@infosys.com"):
        with pytest.raises(BadRequestException):
            normalize_email(bad)


async def test_work_email_is_verified_by_code(async_client, people, outbox):
    address = f"person.a.{people.tag}@acme-{people.tag}.com"
    res = await _send(async_client, people.a, address)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email_domain"] == f"acme-{people.tag}.com"
    assert len(outbox) == 1 and outbox[0].to == address
    code = _code_from(outbox[0])
    assert body["dev_code"] == code  # echoed only in development/test
    assert code not in outbox[0].subject

    # The address itself is never stored: only the domain and a keyed hash.
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Verification).where(Verification.user_id == people.a))).scalar_one()
        assert row.status == "pending" and row.method == "email_code"
        assert address not in {row.subject_hash, row.code_hash, row.email_domain, row.document_url}
        assert row.code_hash != code

    status = (await async_client.get(f"{API}/verification/status", headers=_auth(people.a))).json()
    assert status["pending"]["email_domain"] == f"acme-{people.tag}.com"
    assert status["badges"] == [] and status["id_verification_available"] is False

    wrong = "000000" if code != "000000" else "111111"
    assert (await _confirm(async_client, people.a, wrong)).status_code == 400
    res = await _confirm(async_client, people.a, code)
    assert res.status_code == 200, res.text
    status = res.json()
    assert status["badges"] == ["work_email"]
    assert status["verifications"][0]["email_domain"] == f"acme-{people.tag}.com"
    assert status["pending"] is None
    assert status["total_trust_score"] == 70  # base 30 + email 40
    assert status["is_fully_verified"] is False  # mobile number not verified yet

    async with AsyncSessionLocal() as s:
        user = await s.get(User, people.a)
        assert user.is_verified is True
        row = (await s.execute(select(Verification).where(Verification.user_id == people.a))).scalar_one()
        assert row.status == "approved" and row.code_hash is None and row.verified_at is not None

    # A used code can't be replayed, and asking again for the same address is a no-op.
    assert (await _confirm(async_client, people.a, code)).status_code == 400
    await _skip_cooldown(people.a)
    again = (await _send(async_client, people.a, address.upper())).json()
    assert again["already_verified"] is True and len(outbox) == 1


async def test_phone_and_email_make_a_fully_verified_member(async_client, people, outbox):
    async with AsyncSessionLocal() as s:
        await s.execute(update(User).where(User.id == people.a)
                        .values(phone_number=f"+9198{people.tag[:8].translate(str.maketrans('abcdef', '123456'))}",
                                phone_verified_at=datetime.now(timezone.utc)))
        await s.commit()
    await _send(async_client, people.a, f"a@college-{people.tag}.ac.in", STUDENT_EMAIL)
    status = (await _confirm(async_client, people.a, _code_from(outbox[-1]))).json()
    assert status["badges"] == ["phone", "student_email"]
    assert status["is_fully_verified"] is True and status["total_trust_score"] == 100


async def test_one_address_one_account(async_client, people, outbox):
    address = f"shared.{people.tag}@acme-{people.tag}.com"
    await _send(async_client, people.a, address)
    assert (await _confirm(async_client, people.a, _code_from(outbox[-1]))).status_code == 200

    # Someone else who can read that inbox still can't attach it to a second account.
    await _send(async_client, people.b, address)
    res = await _confirm(async_client, people.b, _code_from(outbox[-1]))
    assert res.status_code == 409
    async with AsyncSessionLocal() as s:
        assert (await s.get(User, people.b)).is_verified is False
        assert (await s.get(User, people.a)).is_verified is True


async def test_new_work_email_replaces_the_old_one(async_client, people, outbox):
    await _send(async_client, people.a, f"a@old-{people.tag}.com")
    await _confirm(async_client, people.a, _code_from(outbox[-1]))
    await _skip_cooldown(people.a)
    await _send(async_client, people.a, f"a@new-{people.tag}.com")
    status = (await _confirm(async_client, people.a, _code_from(outbox[-1]))).json()
    assert [v["email_domain"] for v in status["verifications"]] == [f"new-{people.tag}.com"]
    async with AsyncSessionLocal() as s:
        states = sorted((await s.execute(select(Verification.status).where(Verification.user_id == people.a))).scalars())
        assert states == ["approved", "superseded"]


async def test_limits_on_codes(async_client, people, outbox):
    address = f"a@limits-{people.tag}.com"
    assert (await _send(async_client, people.a, address)).status_code == 200
    assert (await _send(async_client, people.a, address)).status_code == 429  # resend cooldown

    # Five wrong guesses burn the code, even if the right one follows.
    code = _code_from(outbox[-1])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS):
        assert (await _confirm(async_client, people.a, wrong)).status_code == 400
    assert (await _confirm(async_client, people.a, code)).status_code == 400

    # An expired code is refused.
    await _skip_cooldown(people.a)
    await _send(async_client, people.a, address)
    async with AsyncSessionLocal() as s:
        await s.execute(update(Verification).where(Verification.user_id == people.a, Verification.status == "pending")
                        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await s.commit()
    assert (await _confirm(async_client, people.a, _code_from(outbox[-1]))).status_code == 400

    # A newer code supersedes the previous one.
    await _skip_cooldown(people.a)
    await _send(async_client, people.a, address)
    first = _code_from(outbox[-1])
    await _skip_cooldown(people.a)
    await _send(async_client, people.a, address)
    second = _code_from(outbox[-1])
    if first != second:
        assert (await _confirm(async_client, people.a, first)).status_code == 400
    assert (await _confirm(async_client, people.a, second)).status_code == 200

    # Hourly cap per address, across accounts (stops flooding someone's inbox).
    target = f"victim@inbox-{people.tag}.com"
    for i in range(settings.OTP_MAX_SENDS_PER_HOUR):
        assert (await _send(async_client, people.b, target)).status_code == 200
        async with AsyncSessionLocal() as s:  # past the cooldown, still within the hour
            await s.execute(update(Verification).where(Verification.user_id == people.b)
                            .values(created_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
            await s.commit()
    assert (await _send(async_client, people.b, target)).status_code == 429


async def test_refused_addresses_send_nothing(async_client, people, outbox):
    assert (await _send(async_client, people.a, "a@gmail.com")).status_code == 400
    assert (await _send(async_client, people.a, f"a@acme-{people.tag}.com", STUDENT_EMAIL)).status_code == 400
    assert (await _send(async_client, people.a, "nonsense")).status_code == 400
    res = await async_client.post(f"{API}/verification/email/send", headers=_auth(people.a),
                                  json={"verification_type": "government_id", "email": "a@acme.com"})
    assert res.status_code == 422
    assert outbox == []


async def test_id_document_checks_are_switched_off(async_client, people):
    res = await async_client.post(f"{API}/verification/submit", headers=_auth(people.a),
                                  json={"verification_type": "government_id", "document_url": "https://x/y.pdf"})
    assert res.status_code in (404, 405)
    res = await async_client.patch(f"{API}/verification/admin/approve/{uuid4()}", headers=_auth(people.a))
    assert res.status_code in (404, 405)

    # Old manual approvals no longer earn a badge or trust points.
    async with AsyncSessionLocal() as s:
        s.add(Verification(user_id=people.a, verification_type="government_id", status="approved",
                           method="manual", document_url="https://documents.example/pending_upload.pdf"))
        await s.commit()
    status = (await async_client.get(f"{API}/verification/status", headers=_auth(people.a))).json()
    assert status["badges"] == [] and status["total_trust_score"] == 30
