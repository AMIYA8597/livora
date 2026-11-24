"""
Staff overriding application status against a real database: who may change what, the reason
staff must give, the history every change leaves, what each side is told, and the staff list.
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.modules.applications.models import Application
from app.modules.notifications.models import Notification
from app.modules.properties.models import Property
from app.modules.users.models import User
from app.workers import outbox

API = settings.API_V1_PREFIX


def _auth(user_id, role="seeker") -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


@pytest.fixture(autouse=True)
def no_background_dispatch(monkeypatch):
    monkeypatch.setattr(outbox, "schedule_dispatch", lambda: None)


@pytest.fixture
async def world():
    w = SimpleNamespace(applicant=uuid4(), owner=uuid4(), mod=uuid4(), stranger=uuid4(),
                        prop=uuid4(), app=uuid4(), tag=uuid4().hex[:8])
    async with AsyncSessionLocal() as s:
        for key, name, role in (("applicant", "Asha Rao", "seeker"), ("owner", "Omar Das", "owner"),
                                ("mod", "Mona Staff", "moderator"), ("stranger", "Sam Other", "seeker")):
            s.add(User(id=getattr(w, key), email=f"ovr-{key}-{w.tag}@example.com", hashed_password="x",
                       full_name=name, role=role))
        await s.flush()
        s.add(Property(
            id=w.prop, owner_id=w.owner, title=f"Quiet room {w.tag}", description="Calm.",
            location=WKTElement("POINT(77.6 12.9)", srid=4326), address_display="HSR Layout, Bengaluru",
            address_exact="2 Calm St", city="Bengaluru", postal_code="560102", monthly_rent=Decimal("15000"),
            available_from=date.today(), listing_status="published", is_active=True,
        ))
        await s.flush()
        s.add(Application(id=w.app, applicant_id=w.applicant, property_id=w.prop, status="submitted",
                          introduction="Hi, I'd like the room.", proposed_rent=Decimal("15000"),
                          move_in_target=date.today() + timedelta(days=20)))
        await s.commit()
    yield w
    async with AsyncSessionLocal() as s:
        users = [w.applicant, w.owner, w.mod, w.stranger]
        await s.execute(delete(Property).where(Property.id == w.prop))
        await s.execute(delete(User).where(User.id.in_(users)))
        await s.commit()


async def _set(client, w, who, status, note=None, role="seeker"):
    body = {"status": status} | ({"note": note} if note is not None else {})
    return await client.patch(f"{API}/applications/{w.app}/status", headers=_auth(who, role), json=body)


async def _notes(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(
            select(Notification).where(Notification.user_id == user_id,
                                       Notification.notification_type == "application_status_change")
        )).scalars().all()


async def test_only_the_right_people_change_status(async_client, world):
    assert (await _set(async_client, world, world.stranger, "accepted")).status_code == 403
    assert (await _set(async_client, world, world.applicant, "accepted")).status_code == 403
    # Unknown statuses are refused for everyone, staff included.
    assert (await _set(async_client, world, world.owner, "banana", role="owner")).status_code == 422
    assert (await _set(async_client, world, world.mod, "banana", note="Testing it", role="moderator")).status_code == 422
    # Owners still follow the normal flow.
    assert (await _set(async_client, world, world.owner, "rejected", role="owner")).status_code == 200
    assert (await _set(async_client, world, world.owner, "accepted", role="owner")).status_code == 400


async def test_staff_override_needs_a_reason_and_is_recorded(async_client, world):
    assert (await _set(async_client, world, world.mod, "rejected", role="moderator")).status_code == 400
    assert (await _set(async_client, world, world.mod, "rejected", note=" ok ", role="moderator")).status_code == 400

    res = await _set(async_client, world, world.mod, "rejected", note="Listing confirmed as a scam", role="moderator")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "rejected"

    # Same status, or back to 'submitted', aren't overrides.
    assert (await _set(async_client, world, world.mod, "rejected", note="Again please", role="moderator")).status_code == 409
    assert (await _set(async_client, world, world.mod, "submitted", note="Start over", role="moderator")).status_code == 400

    history = (await async_client.get(f"{API}/admin/applications/{world.app}/history",
                                      headers=_auth(world.mod, "moderator"))).json()
    assert [(h["from_status"], h["to_status"], h["by_staff"]) for h in history] == [("submitted", "rejected", True)]
    assert history[0]["note"] == "Listing confirmed as a scam" and history[0]["actor_name"] == "Mona Staff"

    # Both sides are told, and told it was support, not the other person.
    [to_applicant] = await _notes(world.applicant)
    assert to_applicant.title == "Your application wasn't successful" and "Flatmate support" in to_applicant.body
    [to_owner] = await _notes(world.owner)
    assert to_owner.title == "Asha's application wasn't successful" and "Flatmate support" in to_owner.body
    assert to_owner.link == "/owner?tab=applications"
    # The reason stays with staff.
    assert "scam" not in to_applicant.body and "scam" not in to_owner.body


async def test_reopening_cannot_duplicate_an_active_application(async_client, world):
    assert (await _set(async_client, world, world.applicant, "withdrawn")).status_code == 200
    async with AsyncSessionLocal() as s:
        s.add(Application(applicant_id=world.applicant, property_id=world.prop, status="submitted",
                          introduction="Trying again.", proposed_rent=Decimal("15000"),
                          move_in_target=date.today() + timedelta(days=30)))
        await s.commit()
    res = await _set(async_client, world, world.mod, "under_review", note="Withdrawn by mistake", role="moderator")
    assert res.status_code == 409

    async with AsyncSessionLocal() as s:
        await s.execute(delete(Application).where(Application.property_id == world.prop, Application.id != world.app))
        await s.commit()
    res = await _set(async_client, world, world.mod, "under_review", note="Withdrawn by mistake", role="moderator")
    assert res.status_code == 200, res.text

    history = (await async_client.get(f"{API}/admin/applications/{world.app}/history",
                                      headers=_auth(world.mod, "moderator"))).json()
    assert [(h["to_status"], h["by_staff"]) for h in history] == [("withdrawn", False), ("under_review", True)]


async def test_staff_can_find_applications(async_client, world):
    h = _auth(world.mod, "moderator")
    found = (await async_client.get(f"{API}/admin/applications", headers=h, params={"q": world.tag})).json()
    assert [a["id"] for a in found] == [str(world.app)]
    assert found[0]["applicant_name"] == "Asha Rao" and found[0]["owner_name"] == "Omar Das"
    by_email = (await async_client.get(f"{API}/admin/applications", headers=h,
                                       params={"q": f"ovr-applicant-{world.tag}"})).json()
    assert [a["id"] for a in by_email] == [str(world.app)]
    none = (await async_client.get(f"{API}/admin/applications", headers=h,
                                   params={"q": world.tag, "status": "accepted"})).json()
    assert none == []
    # LIKE wildcards in the search are literal.
    assert (await async_client.get(f"{API}/admin/applications", headers=h, params={"q": "%_%" + world.tag})).json() == []

    assert (await async_client.get(f"{API}/admin/applications", headers=_auth(world.owner, "owner"))).status_code == 403
    assert (await async_client.get(f"{API}/admin/applications/{world.app}/history",
                                   headers=_auth(world.applicant))).status_code == 403
    assert (await async_client.get(f"{API}/admin/applications/{uuid4()}/history", headers=h)).status_code == 404


# --------------------------------------------------------------------------- history for the parties

async def test_applicant_and_owner_see_the_timeline_without_staff_details(async_client, world):
    assert (await _set(async_client, world, world.owner, "under_review", role="owner")).status_code == 200
    assert (await _set(async_client, world, world.mod, "rejected", note="Listing confirmed as a scam",
                       role="moderator")).status_code == 200
    assert (await _set(async_client, world, world.mod, "under_review", note="Owner verified after all",
                       role="moderator")).status_code == 200
    assert (await _set(async_client, world, world.applicant, "withdrawn")).status_code == 200

    expected = [
        (None, "submitted", "applicant"),
        ("submitted", "under_review", "owner"),
        ("under_review", "rejected", "support"),
        ("rejected", "under_review", "support"),
        ("under_review", "withdrawn", "applicant"),
    ]
    for who, role in ((world.applicant, "seeker"), (world.owner, "owner")):
        res = await async_client.get(f"{API}/applications/{world.app}/history", headers=_auth(who, role))
        assert res.status_code == 200, res.text
        timeline = res.json()
        assert [(h["from_status"], h["to_status"], h["actor"]) for h in timeline] == expected
        times = [h["created_at"] for h in timeline]
        assert times == sorted(times)
        # Who on the staff acted, and why, stays with staff.
        raw = res.text
        assert "scam" not in raw and "verified after all" not in raw and "Mona" not in raw
        assert str(world.mod) not in raw
        assert set(timeline[0]) == {"from_status", "to_status", "actor", "created_at"}


async def test_history_is_private_to_the_application(async_client, world):
    res = await async_client.get(f"{API}/applications/{world.app}/history", headers=_auth(world.stranger))
    assert res.status_code == 403
    res = await async_client.get(f"{API}/applications/{uuid4()}/history", headers=_auth(world.applicant))
    assert res.status_code == 404
    assert (await async_client.get(f"{API}/applications/{world.app}/history")).status_code in (401, 403)


async def test_moderator_console_access_matches_the_web_tabs(async_client, world):
    """The admin console shows moderators the moderation queue and applications only
    (apps/web/lib/staff-access.ts); the API must agree on both sides of that line."""
    h = _auth(world.mod, "moderator")
    for path in ("/moderation/reports", "/admin/applications", f"/admin/applications/{world.app}/history"):
        assert (await async_client.get(f"{API}{path}", headers=h)).status_code == 200, path
    for path in ("/admin/stats", "/admin/users"):
        assert (await async_client.get(f"{API}{path}", headers=h)).status_code == 403, path
    res = await async_client.patch(f"{API}/admin/users/{world.stranger}/status", headers=h, json={"is_active": False})
    assert res.status_code == 403
    res = await async_client.patch(f"{API}/properties/{world.prop}/status", headers=h,
                                   json={"listing_status": "archived"})
    assert res.status_code == 403
    async with AsyncSessionLocal() as s:
        assert (await s.get(User, world.stranger)).is_active
        assert (await s.get(Property, world.prop)).listing_status == "published"
