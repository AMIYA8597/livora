"""
Account export and deletion (DPDP) against a real database: what the download holds, the
30-day grace (hidden, signed out, cancelled by signing in, locked by staff), and what erasure
removes, keeps and tells other people.
"""
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, get_password_hash
from app.infrastructure.storage import LocalStorageProvider
from app.modules.applications.models import Application
from app.modules.groups.models import Group, GroupMember
from app.modules.messaging.models import Conversation, ConversationParticipant, Message, OutboxEvent
from app.modules.notifications.models import Notification, PushSubscription
from app.modules.properties.models import Property
from app.modules.users import privacy
from app.modules.users.models import AccountDeletionRequest, User
from app.workers import outbox

API = settings.API_V1_PREFIX
PASSWORD = "Correct-horse-42"


def _auth(user_id, role="owner") -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


@pytest.fixture(autouse=True)
def quiet_side_effects(monkeypatch):
    monkeypatch.setattr(outbox, "schedule_dispatch", lambda: None)

    async def no_dispatch():
        return None

    from app.modules.notifications import emails
    monkeypatch.setattr(emails, "dispatch_now", no_dispatch)
    removed = []
    monkeypatch.setattr(privacy, "_remove_files", lambda prefixes: removed.extend(prefixes))
    return removed


@pytest.fixture
async def world():
    w = SimpleNamespace(owner=uuid4(), seeker=uuid4(), prop=uuid4(), app=uuid4(), group=uuid4(),
                        conv=uuid4(), msg=uuid4(), tag=uuid4().hex[:8])
    w.owner_email = f"del-owner-{w.tag}@example.com"
    async with AsyncSessionLocal() as s:
        s.add(User(id=w.owner, email=w.owner_email, hashed_password=get_password_hash(PASSWORD),
                   full_name="Dev Owner", phone_number="+919800000001", role="owner"))
        s.add(User(id=w.seeker, email=f"del-seeker-{w.tag}@example.com", hashed_password="x",
                   full_name="Sia Seeker", role="seeker"))
        await s.flush()
        s.add(Property(
            id=w.prop, owner_id=w.owner, title=f"Sunny room {w.tag}", description="Bright.",
            location=WKTElement("POINT(77.6 12.9)", srid=4326), address_display="Indiranagar, Bengaluru",
            address_exact="9 Sun St", city="Bengaluru", postal_code="560038", monthly_rent=Decimal("18000"),
            available_from=date.today(), listing_status="published", is_active=True,
        ))
        s.add(Group(id=w.group, creator_id=w.owner, name=f"Group {w.tag}", target_budget_total=40000,
                    target_city="Bengaluru"))
        s.add(Conversation(id=w.conv))
        await s.flush()
        s.add(Application(id=w.app, applicant_id=w.seeker, property_id=w.prop, status="submitted",
                          introduction="Keen!", proposed_rent=Decimal("18000"),
                          move_in_target=date.today() + timedelta(days=15)))
        s.add_all([
            GroupMember(group_id=w.group, user_id=w.owner, role="leader",
                        joined_at=datetime.now(timezone.utc) - timedelta(days=3)),
            GroupMember(group_id=w.group, user_id=w.seeker, role="member",
                        joined_at=datetime.now(timezone.utc) - timedelta(days=2)),
            ConversationParticipant(conversation_id=w.conv, user_id=w.owner),
            ConversationParticipant(conversation_id=w.conv, user_id=w.seeker),
            PushSubscription(user_id=w.owner, endpoint=f"https://push.example/{w.tag}", p256dh="k" * 20, auth="a" * 16),
        ])
        await s.flush()
        s.add(Message(id=w.msg, conversation_id=w.conv, sender_id=w.owner, content="The room is still free."))
        await s.commit()
    yield w
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Message).where(Message.conversation_id == w.conv))
        await s.execute(delete(Conversation).where(Conversation.id == w.conv))
        await s.execute(delete(Group).where(Group.id == w.group))
        await s.execute(delete(Property).where(Property.id == w.prop))
        await s.execute(delete(Notification).where(Notification.user_id.in_([w.owner, w.seeker])))
        await s.execute(delete(User).where(User.id.in_([w.owner, w.seeker])))
        await s.commit()


async def _user(user_id) -> User:
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(User).where(User.id == user_id))).scalar_one()


async def _listing_status(prop_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(Property.listing_status).where(Property.id == prop_id))).scalar_one_or_none()


async def test_export_holds_their_data_and_no_secrets(async_client, world):
    res = await async_client.get(f"{API}/users/me/export", headers=_auth(world.owner))
    assert res.status_code == 200
    assert res.headers["content-disposition"].startswith('attachment; filename="flatmate-data-')
    assert res.headers["cache-control"] == "no-store"
    data = res.json()
    assert data["account"]["email"] == world.owner_email
    assert [p["title"] for p in data["properties"]] == [f"Sunny room {world.tag}"]
    assert [m["content"] for m in data["messages"]] == ["The room is still free."]
    assert data["groups"][0]["name"] == f"Group {world.tag}"
    assert data["applications"] == []  # applications *to* their listing are the applicant's data
    raw = json.dumps(data)
    for secret in ("hashed_password", "p256dh", "\"auth\"", "endpoint", "code_hash", "location"):
        assert secret not in raw


async def test_deletion_needs_the_password_then_hides_and_signs_out(async_client, world):
    wrong = await async_client.post(f"{API}/users/me/deletion", headers=_auth(world.owner), json={"password": "nope"})
    assert wrong.status_code == 400
    assert (await _user(world.owner)).is_active is True

    res = await async_client.post(f"{API}/users/me/deletion", headers=_auth(world.owner), json={"password": PASSWORD})
    assert res.status_code == 202
    purge_after = datetime.fromisoformat(res.json()["purge_after"])
    assert timedelta(days=29, hours=23) < purge_after - datetime.now(timezone.utc) <= timedelta(days=30)

    assert (await _user(world.owner)).is_active is False
    assert await _listing_status(world.prop) == "paused"
    # Existing tokens stop working at once.
    assert (await async_client.get(f"{API}/users/me", headers=_auth(world.owner))).status_code == 403
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(PushSubscription).where(PushSubscription.user_id == world.owner))).first() is None
        mail = (await s.execute(select(OutboxEvent).where(
            OutboxEvent.payload["template"].astext == "account_deletion_scheduled",
            OutboxEvent.payload["to"].astext == world.owner_email,
        ))).scalars().all()
        assert len(mail) == 1
        await s.execute(delete(OutboxEvent).where(OutboxEvent.id == mail[0].id))
        await s.commit()


async def test_signing_in_during_the_grace_period_cancels(async_client, world):
    await async_client.post(f"{API}/users/me/deletion", headers=_auth(world.owner), json={"password": PASSWORD})
    res = await async_client.post(f"{API}/auth/login", json={"email": world.owner_email, "password": PASSWORD})
    assert res.status_code == 200
    assert res.json()["account_restored"] is True
    assert (await _user(world.owner)).is_active is True
    assert await _listing_status(world.prop) == "published"
    async with AsyncSessionLocal() as s:
        assert await s.get(AccountDeletionRequest, world.owner) is None
    again = await async_client.post(f"{API}/auth/login", json={"email": world.owner_email, "password": PASSWORD})
    assert again.json()["account_restored"] is False


async def test_staff_deactivation_locks_a_pending_deletion(async_client, world):
    await async_client.post(f"{API}/users/me/deletion", headers=_auth(world.owner), json={"password": PASSWORD})
    async with AsyncSessionLocal() as s:
        user = await s.get(User, world.owner)
        await privacy.on_staff_status_change(s, user, False)
        await s.commit()
    res = await async_client.post(f"{API}/auth/login", json={"email": world.owner_email, "password": PASSWORD})
    assert res.status_code == 401
    async with AsyncSessionLocal() as s:
        assert (await s.get(AccountDeletionRequest, world.owner)).cancellable is False


async def test_erasure_after_the_grace_period(async_client, world, quiet_side_effects):
    await async_client.post(f"{API}/users/me/deletion", headers=_auth(world.owner), json={"password": PASSWORD})
    # Not due yet: nothing happens.
    assert await privacy.purge_due_accounts(AsyncSessionLocal) == 0
    async with AsyncSessionLocal() as s:
        await s.execute(update(AccountDeletionRequest).where(AccountDeletionRequest.user_id == world.owner)
                        .values(purge_after=datetime.now(timezone.utc) - timedelta(minutes=1)))
        await s.commit()

    assert await privacy.purge_due_accounts(AsyncSessionLocal) == 1

    tomb = await _user(world.owner)
    assert tomb.full_name == "Deleted user" and tomb.phone_number is None
    assert tomb.email == f"deleted+{world.owner.hex}@deleted.invalid"
    assert tomb.deleted_at is not None and tomb.is_active is False
    assert await _listing_status(world.prop) is None
    async with AsyncSessionLocal() as s:
        assert await s.get(Application, world.app) is None
        assert await s.get(AccountDeletionRequest, world.owner) is None
        # Their message stays in the other person's chat, now from "Deleted user".
        msg = await s.get(Message, world.msg)
        assert msg is not None and msg.sender_id == world.owner
        part = (await s.execute(select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == world.conv, ConversationParticipant.user_id == world.owner,
        ))).scalar_one()
        assert part.is_active is False
        # The group passes to the remaining member.
        group = await s.get(Group, world.group)
        assert group.creator_id == world.seeker
        role = (await s.execute(select(GroupMember.role).where(
            GroupMember.group_id == world.group, GroupMember.user_id == world.seeker))).scalar_one()
        assert role == "leader"
        # The applicant is told the listing is gone.
        notes = (await s.execute(select(Notification).where(
            Notification.user_id == world.seeker, Notification.title == "A listing is no longer available",
        ))).scalars().all()
        assert len(notes) == 1 and f"Sunny room {world.tag}" in notes[0].body

    assert ("avatars", f"{world.owner}/") in quiet_side_effects
    assert ("properties", f"prop_{world.prop}/") in quiet_side_effects

    # The old email no longer signs in, and a second run does nothing.
    res = await async_client.post(f"{API}/auth/login", json={"email": world.owner_email, "password": PASSWORD})
    assert res.status_code == 401
    assert await privacy.purge_due_accounts(AsyncSessionLocal) == 0


def test_local_storage_deletes_only_that_folder(tmp_path):
    store = LocalStorageProvider(base_dir=str(tmp_path))
    store.upload_file("avatars", "u1/a.jpg", b"1")
    store.upload_file("avatars", "u1/b.jpg", b"2")
    store.upload_file("avatars", "u2/c.jpg", b"3")
    assert store.delete_prefix("avatars", "u1/") == 2
    assert not (tmp_path / "avatars" / "u1").exists()
    assert (tmp_path / "avatars" / "u2" / "c.jpg").exists()
    assert store.delete_prefix("avatars", "missing/") == 0
    for bad in ("../", "u2", "/u2/", "a/b/"):
        with pytest.raises(ValueError):
            store.delete_prefix("avatars", bad)
