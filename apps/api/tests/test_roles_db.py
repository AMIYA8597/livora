"""
Who can hold which role, against a real database: nobody signs up as staff or broker, admins
grant non-staff roles and moderator, only a super admin makes (or touches) admins, the primary
role and the last super admin stay, and the broker request -> admin approval flow.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core import rate_limit
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.roles import ALL_ROLES, SELF_SERVICE_ROLES, can_grant, can_manage_account
from app.core.security import create_access_token
from app.modules.messaging.models import OutboxEvent
from app.modules.notifications.models import Notification
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.users.models import RoleRequest, User, UserPrivacySetting, UserRole
from app.modules.users.privacy import EXPORT_TABLES, PURGE_DELETE

API = settings.API_V1_PREFIX


def auth(user_id, role="seeker"):
    # The token's role list is decoration: every check reads the roles from the database.
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


# ---------------------------------------------------------------- pure rules

def test_who_may_grant_what():
    assert can_grant({"super_admin"}, "admin") and can_grant({"super_admin"}, "super_admin")
    assert can_grant({"admin"}, "moderator") and can_grant({"admin"}, "broker")
    assert not can_grant({"admin"}, "admin") and not can_grant({"admin"}, "super_admin")
    assert not can_grant({"moderator"}, "broker") and not can_grant({"seeker"}, "seeker")
    assert not can_grant({"super_admin"}, "wizard")
    assert can_manage_account({"admin"}, {"seeker", "moderator"})
    assert not can_manage_account({"admin"}, {"seeker", "admin"})
    assert can_manage_account({"super_admin"}, {"admin"})
    assert SELF_SERVICE_ROLES == {"seeker", "tenant", "owner", "pg_operator"}
    assert {"broker", "moderator", "admin", "super_admin"} <= ALL_ROLES


def test_role_requests_are_exported_and_erased_with_the_account():
    assert EXPORT_TABLES["role_requests"] == ("user_id",)
    assert ("role_requests", "user_id") in PURGE_DELETE


# ---------------------------------------------------------------- people

@pytest.fixture
async def people():
    tag = f"Roles{uuid4().hex[:8]}"
    ids = SimpleNamespace(
        seeker=uuid4(), other=uuid4(), moderator=uuid4(), admin=uuid4(), admin2=uuid4(),
        super1=uuid4(), super2=uuid4(),
    )
    extra = {"moderator": ["moderator"], "admin": ["admin"], "admin2": ["admin"],
             "super1": ["super_admin"], "super2": ["super_admin"]}
    async with AsyncSessionLocal() as s:
        for key, uid in vars(ids).items():
            s.add(User(id=uid, email=f"{tag}-{key}@example.com", hashed_password="x",
                       full_name=f"{key.title()} Person", role="seeker"))
        await s.flush()
        for key, roles in extra.items():
            for role in roles:
                s.add(UserRole(user_id=getattr(ids, key), role=role, is_verified=True))
        await s.commit()
    await rate_limit.reset()
    ids.tag = tag
    yield ids

    all_ids = [v for k, v in vars(ids).items() if k != "tag"]
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Notification).where(Notification.user_id.in_(all_ids)))
        await s.execute(delete(RoleRequest).where(RoleRequest.user_id.in_(all_ids)))
        await s.execute(delete(User).where(User.id.in_(all_ids)))
        await s.commit()


async def _roles(client, admin, user_id):
    res = await client.get(f"{API}/admin/users?limit=100", headers=auth(admin))
    assert res.status_code == 200, res.text
    return next(u["roles"] for u in res.json() if u["id"] == str(user_id))


# ---------------------------------------------------------------- sign-up

@pytest.mark.parametrize("body", [
    {"role": "admin"},
    {"role": "super_admin"},
    {"role": "moderator"},
    {"role": "broker"},
    {"role": "seeker", "additional_roles": ["admin"]},
    {"role": "owner", "additional_roles": ["super_admin", "tenant"]},
    {"role": "seeker", "additional_roles": ["broker"]},
])
async def test_nobody_signs_up_as_staff_or_broker(async_client, body):
    await rate_limit.reset()
    email = f"signup-{uuid4().hex[:10]}@example.com"
    res = await async_client.post(f"{API}/auth/register", json={
        "email": email, "password": "A-strong-pass-123", "full_name": "Eve Escalate", **body,
    })
    assert res.status_code == 422, res.text
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(func.count()).select_from(User).where(User.email == email))).scalar() == 0


async def test_self_service_roles_still_sign_up(async_client):
    await rate_limit.reset()
    email = f"signup-{uuid4().hex[:10]}@example.com"
    res = await async_client.post(f"{API}/auth/register", json={
        "email": email, "password": "A-strong-pass-123", "full_name": "Pia Operator",
        "role": "pg_operator", "additional_roles": ["owner"],
    })
    try:
        assert res.status_code == 201, res.text
        assert sorted(res.json()["roles"]) == ["owner", "pg_operator"]
    finally:
        async with AsyncSessionLocal() as s:
            uid = (await s.execute(select(User.id).where(User.email == email))).scalar_one()
            await s.execute(delete(UserPrivacySetting).where(UserPrivacySetting.user_id == uid))
            await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["to"].astext == email))
            await s.execute(delete(User).where(User.id == uid))
            await s.commit()


# ---------------------------------------------------------------- granting and removing

async def test_admins_grant_non_staff_roles_and_moderator_only(async_client, people):
    grant = lambda actor, uid, role: async_client.post(  # noqa: E731
        f"{API}/admin/users/{uid}/roles", headers=auth(actor), json={"role": role})

    res = await grant(people.admin, people.seeker, "moderator")
    assert res.status_code == 201, res.text
    assert res.json()["roles"] == ["moderator", "seeker"]
    assert (await grant(people.admin, people.seeker, "broker")).status_code == 201

    assert (await grant(people.admin, people.seeker, "admin")).status_code == 403
    assert (await grant(people.admin, people.seeker, "super_admin")).status_code == 403
    assert (await grant(people.admin, people.admin, "super_admin")).status_code == 403  # no self-promotion
    assert (await grant(people.admin, people.seeker, "wizard")).status_code == 400
    assert (await grant(people.moderator, people.seeker, "broker")).status_code == 403
    assert (await grant(people.seeker, people.other, "owner")).status_code == 403

    res = await grant(people.super1, people.other, "admin")
    assert res.status_code == 201 and "admin" in res.json()["roles"]


async def test_removing_roles(async_client, people):
    revoke = lambda actor, uid, role: async_client.delete(  # noqa: E731
        f"{API}/admin/users/{uid}/roles/{role}", headers=auth(actor))

    res = await revoke(people.admin, people.moderator, "moderator")
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["seeker"]
    assert (await revoke(people.admin, people.moderator, "moderator")).status_code == 404
    assert (await revoke(people.admin, people.seeker, "seeker")).status_code == 400  # the primary role
    assert (await revoke(people.admin, people.admin2, "admin")).status_code == 403
    assert (await revoke(people.super1, people.admin2, "admin")).status_code == 200

    async with AsyncSessionLocal() as s:
        others = (await s.execute(
            select(func.count()).select_from(UserRole).join(User, User.id == UserRole.user_id)
            .where(UserRole.role == "super_admin", User.is_active.is_(True),
                   UserRole.user_id.notin_([people.super1, people.super2]))
        )).scalar()
    if others:
        pytest.skip("Other super admins exist in this database; the last-one rule can't be isolated")
    assert (await revoke(people.super1, people.super2, "super_admin")).status_code == 200
    res = await revoke(people.super1, people.super1, "super_admin")
    assert res.status_code == 400 and "at least one" in res.text


async def test_only_a_super_admin_changes_an_admin_account(async_client, people):
    status = lambda actor, uid, active: async_client.patch(  # noqa: E731
        f"{API}/admin/users/{uid}/status", headers=auth(actor), json={"is_active": active})

    assert (await status(people.admin, people.admin2, False)).status_code == 403
    assert (await status(people.admin, people.super1, False)).status_code == 403
    assert (await status(people.admin, people.admin, False)).status_code == 400  # not yourself
    res = await status(people.admin, people.moderator, False)
    assert res.status_code == 200 and res.json()["is_active"] is False
    assert (await status(people.super1, people.admin2, False)).status_code == 200


async def test_a_removed_role_stops_working_at_once(async_client, people):
    # The moderator's token still says "moderator"; the database decides.
    queue = lambda: async_client.get(f"{API}/admin/applications", headers=auth(people.moderator, "moderator"))  # noqa: E731
    assert (await queue()).status_code == 200
    await async_client.delete(f"{API}/admin/users/{people.moderator}/roles/moderator", headers=auth(people.admin))
    assert (await queue()).status_code == 403


async def test_listing_admin_view_reads_roles_from_the_database(async_client, people):
    async with AsyncSessionLocal() as s:
        pid = (await PropertyService(s).create(people.other, PropertyCreate(
            title=f"{people.tag} flat", description="Flat.", property_category="apartment", configuration="1BHK",
            latitude=25.6751, longitude=94.1086, address_display=f"{people.tag} Colony, Kohima",
            address_exact="7 Secret Lane", city="Kohima", state="Nagaland", postal_code="797001",
            monthly_rent=Decimal("12000"), max_capacity=2, available_from=date.today(), currency="INR",
        )))["id"]
    try:
        # A token claiming admin for someone who isn't: the exact address stays hidden.
        forged = await async_client.get(f"{API}/properties/{pid}", headers=auth(people.seeker, "admin"))
        assert forged.status_code == 200 and forged.json()["address_exact"] != "7 Secret Lane"
        real = await async_client.get(f"{API}/properties/{pid}", headers=auth(people.admin, "admin"))
        assert real.json()["address_exact"] == "7 Secret Lane"
        anonymous = await async_client.get(f"{API}/properties/{pid}")
        assert anonymous.status_code == 200 and anonymous.json()["address_exact"] != "7 Secret Lane"

        # Editing someone else's listing: a granted admin may (their main role is still seeker);
        # a forged admin claim may not.
        edit = lambda who, role: async_client.put(  # noqa: E731
            f"{API}/properties/{pid}", headers=auth(who, role), json={"title": f"{people.tag} flat, fixed"})
        assert (await edit(people.seeker, "admin")).status_code == 403
        assert (await edit(people.admin, "admin")).status_code == 200
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["entity_id"].astext == str(pid)))
            await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["property_id"].astext == str(pid)))
            await s.execute(delete(Property).where(Property.id == pid))
            await s.commit()


async def test_every_lister_gets_the_listings_dashboard(async_client, people):
    """Owners, PG operators and brokers can all list, so all of them manage listings there."""
    dashboard = lambda uid: async_client.get(f"{API}/owners/properties", headers=auth(uid))  # noqa: E731
    assert (await dashboard(people.seeker)).status_code == 403
    for role in ("broker", "pg_operator", "owner"):
        res = await async_client.post(f"{API}/admin/users/{people.seeker}/roles", headers=auth(people.admin),
                                      json={"role": role})
        assert res.status_code == 201, res.text
        assert (await dashboard(people.seeker)).status_code == 200, role
        await async_client.delete(f"{API}/admin/users/{people.seeker}/roles/{role}", headers=auth(people.admin))
        assert (await dashboard(people.seeker)).status_code == 403, role


# ---------------------------------------------------------------- broker requests

async def test_broker_request_approved_by_an_admin(async_client, people):
    ask = lambda uid, body: async_client.post(f"{API}/users/me/role-requests", headers=auth(uid), json=body)  # noqa: E731

    assert (await ask(people.seeker, {"role": "admin"})).status_code == 422
    res = await ask(people.seeker, {"role": "broker", "note": "Agency: Kohima Homes, RERA NL-123"})
    assert res.status_code == 201, res.text
    request_id = res.json()["id"]
    assert res.json()["status"] == "pending"
    assert (await ask(people.seeker, {"role": "broker"})).status_code == 409  # one open request

    mine = (await async_client.get(f"{API}/users/me/role-requests", headers=auth(people.seeker))).json()
    assert [r["id"] for r in mine] == [request_id]

    # Only admins see and decide the queue.
    assert (await async_client.get(f"{API}/admin/role-requests", headers=auth(people.moderator))).status_code == 403
    queue = (await async_client.get(f"{API}/admin/role-requests", headers=auth(people.admin))).json()
    item = next(r for r in queue if r["id"] == request_id)
    assert item["user_email"].startswith(people.tag) and item["note"].startswith("Agency")

    decide = lambda actor, body: async_client.post(  # noqa: E731
        f"{API}/admin/role-requests/{request_id}/decision", headers=auth(actor), json=body)
    assert (await decide(people.moderator, {"approve": True})).status_code == 403
    res = await decide(people.admin, {"approve": True, "note": "Checked RERA"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved" and "broker" in res.json()["user_roles"]
    assert (await decide(people.admin, {"approve": False, "note": "no"})).status_code == 409

    assert "broker" in await _roles(async_client, people.admin, people.seeker)
    assert (await ask(people.seeker, {"role": "broker"})).status_code == 400  # already a broker
    async with AsyncSessionLocal() as s:
        note = (await s.execute(select(Notification).where(
            Notification.user_id == people.seeker, Notification.notification_type == "role_request_result",
        ))).scalar_one()
        assert "verified broker" in note.title and note.link == "/profile"


async def test_broker_request_declined_with_a_reason(async_client, people):
    res = await async_client.post(f"{API}/users/me/role-requests", headers=auth(people.other), json={"role": "broker"})
    request_id = res.json()["id"]
    url = f"{API}/admin/role-requests/{request_id}/decision"

    assert (await async_client.post(url, headers=auth(people.admin), json={"approve": False})).status_code == 400
    res = await async_client.post(url, headers=auth(people.admin),
                                  json={"approve": False, "note": "Please add your RERA number."})
    assert res.status_code == 200 and res.json()["status"] == "declined"
    assert "broker" not in await _roles(async_client, people.admin, people.other)

    mine = (await async_client.get(f"{API}/users/me/role-requests", headers=auth(people.other))).json()
    assert mine[0]["decision_note"] == "Please add your RERA number."
    declined = (await async_client.get(f"{API}/admin/role-requests?status=declined", headers=auth(people.admin))).json()
    assert any(r["id"] == request_id for r in declined)
    # Declined, they can ask again with the missing detail.
    again = await async_client.post(f"{API}/users/me/role-requests", headers=auth(people.other),
                                    json={"role": "broker", "note": "RERA NL-456"})
    assert again.status_code == 201
