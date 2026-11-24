"""
Notification centre and Web Push against a real database: paging and read state, the events
that create notifications (match, like, application, visit, chat), push subscriptions (push
service allow-list), preferences, delivery through the outbox, and cleanup of dead browsers.
"""
import base64
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.modules.messaging.models import OutboxEvent
from app.modules.notifications import push as push_module
from app.modules.notifications.models import Notification, PushSubscription
from app.modules.notifications.service import NotificationService, safe_link
from app.modules.notifications.vapid import generate
from app.modules.profiles.models import Profile
from app.modules.properties.models import Property
from app.modules.users.models import User
from app.workers import outbox
from app.workers.outbox import dispatch_pending

API = settings.API_V1_PREFIX


def _auth(user_id, role="seeker") -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(os.urandom(n)).rstrip(b"=").decode()


def _sub(host="fcm.googleapis.com"):
    return {"endpoint": f"https://{host}/fcm/send/{uuid4().hex}", "keys": {"p256dh": _b64(65), "auth": _b64(16)}}


@pytest.fixture(autouse=True)
def no_background_dispatch(monkeypatch):
    """Tests dispatch the outbox themselves, so nothing races them."""
    monkeypatch.setattr(outbox, "schedule_dispatch", lambda: None)


@pytest.fixture
def pushes(monkeypatch):
    """Push configured, with deliveries captured instead of sent."""
    public, private = generate()
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", public)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", private)
    sent = []
    gone = set()

    def sender(info, data, ttl, urgency):
        if info["endpoint"] in gone:
            raise push_module.PushGone()
        sent.append(SimpleNamespace(endpoint=info["endpoint"], data=json.loads(data), ttl=ttl, urgency=urgency))

    push_module.set_sender(sender)
    yield SimpleNamespace(sent=sent, gone=gone)
    push_module.set_sender(None)


@pytest.fixture
async def people():
    ids = SimpleNamespace(a=uuid4(), b=uuid4(), owner=uuid4(), prop=uuid4(), tag=uuid4().hex[:6])
    async with AsyncSessionLocal() as s:
        for key, name, role in (("a", "Asha Rao", "seeker"), ("b", "Bilal Khan", "seeker"), ("owner", "Omar Das", "owner")):
            s.add(User(id=getattr(ids, key), email=f"ntf-{key}-{ids.tag}@example.com", hashed_password="x",
                       full_name=name, role=role))
        await s.flush()
        for key in ("a", "b"):
            s.add(Profile(user_id=getattr(ids, key), display_name=key.upper(), budget_min=10000, budget_max=20000))
        s.add(Property(
            id=ids.prop, owner_id=ids.owner, title="Sunny room in HSR", description="Bright and airy.",
            location=WKTElement("POINT(77.6 12.9)", srid=4326), address_display="HSR Layout, Bengaluru",
            address_exact="1 Bell St", city=f"Bellpur{ids.tag}", postal_code="560102", monthly_rent=Decimal("15000"),
            available_from=date.today(), listing_status="published", is_active=True,
        ))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        users = [ids.a, ids.b, ids.owner]
        await s.execute(delete(OutboxEvent).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT,
            OutboxEvent.payload["user_id"].astext.in_([str(u) for u in users]),
        ))
        await s.execute(delete(Property).where(Property.id == ids.prop))
        await s.execute(delete(User).where(User.id.in_(users)))
        await s.commit()


async def _notifications(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(
            select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at)
        )).scalars().all()


def test_links_stay_on_site():
    assert safe_link("/matches") == "/matches"
    assert safe_link("/messages?conversationId=1") == "/messages?conversationId=1"
    for bad in ("https://evil.example", "//evil.example", "javascript:alert(1)", "/\\evil", None, ""):
        assert safe_link(bad) is None


def test_only_real_push_services_are_accepted():
    ok = _sub()
    push_module.validate_subscription(ok["endpoint"], **ok["keys"])
    for host in ("updates.push.services.mozilla.com", "wns2-pn1p.notify.windows.com", "web.push.apple.com"):
        push_module.validate_subscription(f"https://{host}/x", **ok["keys"])
    for endpoint in ("http://fcm.googleapis.com/x", "https://evil.example/x", "https://fcm.googleapis.com.evil.example/x",
                     "https://localhost/x", "https://169.254.169.254/latest", "https://fcm.googleapis.com:8443/x",
                     "https://user:pw@fcm.googleapis.com/x"):
        with pytest.raises(Exception):
            push_module.validate_subscription(endpoint, **ok["keys"])
    with pytest.raises(Exception):
        push_module.validate_subscription(ok["endpoint"], p256dh=_b64(10), auth=ok["keys"]["auth"])


async def test_centre_paging_and_read_state(async_client, people):
    async with AsyncSessionLocal() as s:
        base = datetime.now(timezone.utc) - timedelta(hours=1)
        for i in range(25):
            s.add(Notification(user_id=people.a, title=f"N{i}", body="b", notification_type="billing",
                               category="account", created_at=base + timedelta(minutes=i)))
        await s.commit()
    h = _auth(people.a)
    first = (await async_client.get(f"{API}/notifications/", params={"limit": 20}, headers=h)).json()
    assert [n["title"] for n in first[:2]] == ["N24", "N23"] and len(first) == 20
    rest = (await async_client.get(f"{API}/notifications/", params={"before": first[-1]["created_at"]}, headers=h)).json()
    assert [n["title"] for n in rest] == [f"N{i}" for i in range(4, -1, -1)]
    assert (await async_client.get(f"{API}/notifications/unread-count", headers=h)).json()["unread_count"] == 25

    one = first[0]["id"]
    assert (await async_client.patch(f"{API}/notifications/{one}/read", headers=h)).json()["is_read"] is True
    # Someone else's notification is not found, not readable.
    assert (await async_client.patch(f"{API}/notifications/{one}/read", headers=_auth(people.b))).status_code == 404
    assert (await async_client.post(f"{API}/notifications/read-all", headers=h)).json()["updated"] == 24
    assert (await async_client.get(f"{API}/notifications/unread-count", headers=h)).json()["unread_count"] == 0


async def test_events_create_linked_notifications(async_client, people):
    # A like names nobody (seeing who is a paid perk); the like back makes a match for both.
    res = await async_client.post(f"{API}/matching/interactions", headers=_auth(people.a),
                                  json={"target_user_id": str(people.b), "action": "like"})
    assert res.status_code == 200, res.text
    [like] = await _notifications(people.b)
    assert like.notification_type == "new_interest" and "Asha" not in like.title and like.link == "/matches"
    res = await async_client.post(f"{API}/matching/interactions", headers=_auth(people.b),
                                  json={"target_user_id": str(people.a), "action": "like"})
    assert res.status_code == 200 and res.json()["is_mutual_match"] is True, res.text
    assert any(n.notification_type == "match_created" and "Bilal" in n.title for n in await _notifications(people.a))
    assert any(n.notification_type == "match_created" and "Asha" in n.title for n in await _notifications(people.b))

    # Application: the owner hears about it, then the applicant hears the decision.
    res = await async_client.post(f"{API}/applications/", headers=_auth(people.a),
                                  json={"property_id": str(people.prop), "introduction": "Hi, I'm tidy and quiet.",
                                        "proposed_rent": 15000, "move_in_target": (date.today() + timedelta(days=30)).isoformat()})
    assert res.status_code == 201, res.text
    app_id = res.json()["id"]
    [received] = [n for n in await _notifications(people.owner) if n.notification_type == "application_received"]
    assert received.title == "New application from Asha" and received.link == "/owner?tab=applications"
    res = await async_client.patch(f"{API}/applications/{app_id}/status", headers=_auth(people.owner, "owner"),
                                   json={"status": "accepted"})
    assert res.status_code == 200, res.text
    [decided] = [n for n in await _notifications(people.a) if n.notification_type == "application_status_change"]
    assert decided.title == "Your application was accepted" and decided.link == "/dashboard?tab=applications"

    # Visit: requested to the host, confirmed back to the visitor.
    when = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    res = await async_client.post(f"{API}/appointments/", headers=_auth(people.b), json={
        "property_id": str(people.prop), "host_id": str(people.owner), "appointment_type": "in_person",
        "scheduled_at": when.isoformat(),
    })
    assert res.status_code == 201, res.text
    [asked] = [n for n in await _notifications(people.owner) if n.notification_type == "appointment_requested"]
    assert asked.title == "Bilal wants to visit" and "IST" in asked.body and asked.category == "rentals"
    await async_client.patch(f"{API}/appointments/{res.json()['id']}/status", headers=_auth(people.owner, "owner"),
                             json={"status": "confirmed"})
    [confirmed] = [n for n in await _notifications(people.b) if n.notification_type == "appointment_status_change"]
    assert confirmed.title == "Your visit is confirmed" and confirmed.link == "/dashboard?tab=appointments"


async def test_chat_notifications_never_carry_the_text(async_client, people):
    res = await async_client.post(f"{API}/messaging/conversations", headers=_auth(people.a),
                                  json={"participant_user_ids": [str(people.b)], "type": "direct"})
    assert res.status_code in (200, 201), res.text
    conv_id = res.json()["conversation_id"]
    secret = f"my upi is asha{people.tag}@okbank"
    res = await async_client.post(f"{API}/messaging/messages", headers=_auth(people.a),
                                  json={"conversation_id": conv_id, "content": secret})
    assert res.status_code in (200, 201), res.text
    [n] = [n for n in await _notifications(people.b) if n.notification_type == "new_message"]
    assert n.title == "New message from Asha" and secret not in n.body and "okbank" not in n.body
    assert n.link == f"/messages?conversationId={conv_id}" and n.category == "messages"

    async def send(text):
        r = await async_client.post(f"{API}/messaging/messages", headers=_auth(people.a),
                                    json={"conversation_id": conv_id, "content": text})
        assert r.status_code in (200, 201), r.text

    # A burst in the same chat is one unread notification...
    await send("are you there?")
    assert len([x for x in await _notifications(people.b) if x.notification_type == "new_message"]) == 1
    # ...but once it's been read, the next message notifies again.
    res = await async_client.patch(f"{API}/notifications/{n.id}/read", headers=_auth(people.b))
    assert res.status_code == 200, res.text
    await send("hello again")
    assert len([x for x in await _notifications(people.b) if x.notification_type == "new_message"]) == 2


async def test_push_subscription_preferences_and_delivery(async_client, people, pushes):
    h = _auth(people.a)
    config = (await async_client.get(f"{API}/notifications/push/config")).json()
    assert config["enabled"] is True and len(config["public_key"]) > 80

    phone, laptop = _sub(), _sub("updates.push.services.mozilla.com")
    assert (await async_client.post(f"{API}/notifications/push/subscriptions", json=phone, headers=h)).json()["devices"] == 1
    assert (await async_client.post(f"{API}/notifications/push/subscriptions", json=laptop, headers=h)).json()["devices"] == 2
    bad = {**_sub(), "endpoint": "https://169.254.169.254/latest/meta-data"}
    assert (await async_client.post(f"{API}/notifications/push/subscriptions", json=bad, headers=h)).status_code == 400

    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(
            people.a, "Your plan is active", "Seeker Pro is on.", "billing", link="/pricing")
    await dispatch_pending(AsyncSessionLocal)
    assert {p.endpoint for p in pushes.sent} == {phone["endpoint"], laptop["endpoint"]}
    payload = pushes.sent[0].data
    assert payload["title"] == "Your plan is active" and payload["url"] == "/pricing" and payload["tag"] == payload["id"]
    assert pushes.sent[0].urgency == "normal"

    # Turning a category off stops its pushes; the in-app notification is still kept.
    prefs = (await async_client.put(f"{API}/notifications/preferences", json={"account": False}, headers=h)).json()
    assert prefs == {"messages": True, "matches": True, "rentals": True, "account": False}
    pushes.sent.clear()
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(people.a, "Renewed", "Thanks.", "billing", reference_id=uuid4())
    await dispatch_pending(AsyncSessionLocal)
    assert pushes.sent == [] and any(n.title == "Renewed" for n in await _notifications(people.a))

    # A browser the push service says is gone is removed; the other keeps working.
    pushes.gone.add(laptop["endpoint"])
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(people.a, "It's a match with Bilal!", "Say hello.",
                                                         "match_created", reference_id=uuid4(), link="/matches")
    await dispatch_pending(AsyncSessionLocal)
    assert [p.endpoint for p in pushes.sent] == [phone["endpoint"]]
    async with AsyncSessionLocal() as s:
        endpoints = (await s.execute(select(PushSubscription.endpoint).where(PushSubscription.user_id == people.a))).scalars().all()
    assert endpoints == [phone["endpoint"]]

    # The same browser signing in as someone else moves to that account; unsubscribe removes it.
    assert (await async_client.post(f"{API}/notifications/push/subscriptions", json=phone, headers=_auth(people.b))).json()["devices"] == 1
    async with AsyncSessionLocal() as s:
        owner = (await s.execute(select(PushSubscription.user_id).where(PushSubscription.endpoint == phone["endpoint"]))).scalar_one()
    assert owner == people.b
    res = await async_client.post(f"{API}/notifications/push/unsubscribe", json={"endpoint": phone["endpoint"]}, headers=_auth(people.b))
    assert res.json()["devices"] == 0


async def test_message_pushes_skip_people_who_are_online(people, pushes, monkeypatch):
    async with AsyncSessionLocal() as s:
        sub = _sub()
        s.add(PushSubscription(user_id=people.b, endpoint=sub["endpoint"], **sub["keys"]))
        await s.commit()

    async def online(_user_id):
        return True

    from app.modules.notifications import service as notification_service
    monkeypatch.setattr(notification_service, "_is_online", online)
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(people.b, "New message from Asha", "Open the chat.",
                                                         "new_message", reference_id=uuid4())
        await NotificationService(s).create_notification(people.b, "It's a match!", "Say hello.",
                                                         "match_created", reference_id=uuid4())
    await dispatch_pending(AsyncSessionLocal)
    assert [p.data["title"] for p in pushes.sent] == ["It's a match!"]


async def test_without_vapid_keys_nothing_is_queued(async_client, people, monkeypatch):
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", None)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    assert (await async_client.get(f"{API}/notifications/push/config")).json() == {"enabled": False, "public_key": None}
    async with AsyncSessionLocal() as s:
        sub = _sub()
        s.add(PushSubscription(user_id=people.a, endpoint=sub["endpoint"], **sub["keys"]))
        await s.commit()
        await NotificationService(s).create_notification(people.a, "Hi", "b", "billing")
        queued = (await s.execute(select(OutboxEvent.id).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT, OutboxEvent.payload["user_id"].astext == str(people.a),
        ))).scalars().all()
    assert queued == []


async def test_old_notifications_are_purged(people):
    from app.workers.maintenance import run_maintenance

    async with AsyncSessionLocal() as s:
        old = datetime.now(timezone.utc) - timedelta(days=120)
        s.add_all([
            Notification(user_id=people.a, title="old read", body="b", notification_type="billing", is_read=True, created_at=old),
            Notification(user_id=people.a, title="old unread", body="b", notification_type="billing", created_at=old),
            Notification(user_id=people.a, title="ancient", body="b", notification_type="billing",
                         created_at=old - timedelta(days=300)),
        ])
        await s.commit()
    await run_maintenance(AsyncSessionLocal)
    assert [n.title for n in await _notifications(people.a)] == ["old unread"]
    async with AsyncSessionLocal() as s:
        await s.execute(update(Notification).where(Notification.user_id == people.a).values(is_read=True))
        await s.commit()


# --------------------------------------------------------------------------- temporary failures

def test_push_errors_are_classified(monkeypatch):
    import pywebpush
    import requests

    def failing_with(exc):
        def webpush(**_kwargs):
            raise exc
        return webpush

    def http(status, headers=None):
        return pywebpush.WebPushException("x", response=SimpleNamespace(status_code=status, headers=headers or {}))

    info = _sub()
    for exc, expected in (
        (http(503, {"Retry-After": "120"}), push_module.PushRetryable),
        (http(429), push_module.PushRetryable),
        (requests.Timeout(), push_module.PushRetryable),
        (requests.ConnectionError(), push_module.PushRetryable),
        (http(410), push_module.PushGone),
        (http(404), push_module.PushGone),
        (http(400), pywebpush.WebPushException),  # permanent: counted, not retried
        (http(403), pywebpush.WebPushException),
    ):
        monkeypatch.setattr(pywebpush, "webpush", failing_with(exc))
        with pytest.raises(expected) as raised:
            push_module._send_sync(info, "{}", 60, "normal")
        if isinstance(raised.value, push_module.PushRetryable) and getattr(exc, "response", None) is not None:
            assert raised.value.retry_after == (120 if exc.response.status_code == 503 else None)

    assert push_module.retry_delay(1, None) == 30
    assert push_module.retry_delay(2, None) == 60
    assert push_module.retry_delay(1, 120) == 120  # the push service's Retry-After wins
    assert push_module.retry_delay(5, 99_999) == push_module.MAX_RETRY_AFTER_SECONDS


@pytest.fixture
def flaky(monkeypatch):
    """Push configured; endpoints in `down` fail temporarily, everything else is delivered."""
    public, private = generate()
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", public)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", private)
    state = SimpleNamespace(sent=[], down=set(), tries={})

    def sender(info, data, ttl, urgency):
        state.tries[info["endpoint"]] = state.tries.get(info["endpoint"], 0) + 1
        if info["endpoint"] in state.down:
            raise push_module.PushRetryable()
        state.sent.append(info["endpoint"])

    push_module.set_sender(sender)
    yield state
    push_module.set_sender(None)


async def _two_browsers(user_id):
    phone, laptop = _sub(), _sub("updates.push.services.mozilla.com")
    async with AsyncSessionLocal() as s:
        for sub in (phone, laptop):
            s.add(PushSubscription(user_id=user_id, endpoint=sub["endpoint"], **sub["keys"]))
        await s.commit()
    return phone["endpoint"], laptop["endpoint"]


async def _pending_retries(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT,
            OutboxEvent.status == "pending",
            OutboxEvent.payload["user_id"].astext == str(user_id),
        ))).scalars().all()


async def _make_retries_due(user_id):
    async with AsyncSessionLocal() as s:
        await s.execute(update(OutboxEvent).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT,
            OutboxEvent.status == "pending",
            OutboxEvent.payload["user_id"].astext == str(user_id),
        ).values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await s.commit()


async def test_a_temporary_failure_is_retried_for_that_browser_only(people, flaky):
    phone, laptop = await _two_browsers(people.a)
    flaky.down.add(phone)
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(people.a, "Viewing confirmed", "Saturday 11am.",
                                                         "appointment_status_change", reference_id=uuid4())
    started = datetime.now(timezone.utc)
    await dispatch_pending(AsyncSessionLocal)
    assert flaky.sent == [laptop]

    [retry] = await _pending_retries(people.a)
    assert retry.payload["attempt"] == 2 and retry.payload["title"] == "Viewing confirmed"
    async with AsyncSessionLocal() as s:
        phone_sub = (await s.execute(select(PushSubscription).where(PushSubscription.endpoint == phone))).scalar_one()
    assert retry.payload["subscription_ids"] == [str(phone_sub.id)]
    assert retry.next_attempt_at >= started + timedelta(seconds=push_module.RETRY_BASE_SECONDS - 1)
    assert phone_sub.failure_count == 0  # a temporary failure isn't held against the browser

    # Not due yet: nothing happens. Once due, only the phone gets it.
    await dispatch_pending(AsyncSessionLocal)
    assert flaky.sent == [laptop]
    flaky.down.clear()
    await _make_retries_due(people.a)
    await dispatch_pending(AsyncSessionLocal)
    assert flaky.sent == [laptop, phone]
    assert await _pending_retries(people.a) == []


async def test_retries_stop_after_the_limit_and_count_one_failure(people, flaky):
    phone, laptop = await _two_browsers(people.a)
    flaky.down.add(phone)
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(people.a, "New application", "Open it.",
                                                         "application_received", reference_id=uuid4())
    for _ in range(push_module.MAX_PUSH_ATTEMPTS + 2):
        await dispatch_pending(AsyncSessionLocal)
        await _make_retries_due(people.a)
    assert flaky.tries[phone] == push_module.MAX_PUSH_ATTEMPTS
    assert flaky.tries[laptop] == 1
    assert await _pending_retries(people.a) == []
    async with AsyncSessionLocal() as s:
        phone_sub = (await s.execute(select(PushSubscription).where(PushSubscription.endpoint == phone))).scalar_one()
    assert phone_sub.failure_count == 1


async def test_no_retry_once_the_notification_was_read(people, flaky):
    phone, _ = await _two_browsers(people.a)
    flaky.down.add(phone)
    async with AsyncSessionLocal() as s:
        notif = await NotificationService(s).create_notification(people.a, "Visit reminder", "Tomorrow.",
                                                                 "viewing_reminder", reference_id=uuid4())
    await dispatch_pending(AsyncSessionLocal)
    async with AsyncSessionLocal() as s:
        await s.execute(update(Notification).where(Notification.id == notif.id).values(is_read=True))
        await s.commit()
    flaky.down.clear()
    await _make_retries_due(people.a)
    await dispatch_pending(AsyncSessionLocal)
    assert phone not in flaky.sent
    assert await _pending_retries(people.a) == []
