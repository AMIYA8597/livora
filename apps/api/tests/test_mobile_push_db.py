"""
Native push for the Android and iOS apps, against a real database: device registration
(validation, moving between accounts, sign-out), delivery next to Web Push through the outbox,
dead tokens removed, temporary failures retried for that device only, platforms that are off
skipped, and the account export never containing tokens. The FCM/APNs wire format and error
handling are tested without a network.
"""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jose import jwt
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestException
from app.core.security import create_access_token
from app.modules.messaging.models import OutboxEvent
from app.modules.notifications import native_push
from app.modules.notifications import push as push_module
from app.modules.notifications.models import DevicePushToken
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from app.modules.users.privacy import export_user_data
from app.workers import outbox
from app.workers.outbox import dispatch_pending

API = settings.API_V1_PREFIX
IOS_TOKEN = "A1" * 32
ANDROID_TOKEN = "fcm-token_" + "x" * 40 + ":APA91b" + "y" * 60


def _auth(user_id) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=['seeker'])}"}


def _pem(key) -> str:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


@pytest.fixture(autouse=True)
def no_background_dispatch(monkeypatch):
    monkeypatch.setattr(outbox, "schedule_dispatch", lambda: None)


@pytest.fixture
def apps(monkeypatch):
    """Native push on for both platforms (Web Push off); deliveries captured. Tokens in `gone`
    are reported dead, tokens in `down` fail temporarily."""
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", None)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", None)
    for key, value in (("FCM_PROJECT_ID", "flatmate-test"), ("FCM_SERVICE_ACCOUNT_JSON", "{}"),
                       ("APNS_KEY_ID", "KEY123"), ("APNS_TEAM_ID", "TEAM123"),
                       ("APNS_BUNDLE_ID", "app.flatmate.test"), ("APNS_PRIVATE_KEY", "pem")):
        monkeypatch.setattr(settings, key, value)
    state = SimpleNamespace(sent=[], gone=set(), down=set())

    def sender(platform, token, message, ttl, urgency):
        if token in state.gone:
            raise push_module.PushGone()
        if token in state.down:
            raise push_module.PushRetryable()
        state.sent.append(SimpleNamespace(platform=platform, token=token, message=message, ttl=ttl, urgency=urgency))

    native_push.set_sender(sender)
    yield state
    native_push.set_sender(None)


@pytest.fixture
async def people():
    ids = SimpleNamespace(a=uuid4(), b=uuid4(), tag=uuid4().hex[:6])
    async with AsyncSessionLocal() as s:
        for key in ("a", "b"):
            s.add(User(id=getattr(ids, key), email=f"mob-{key}-{ids.tag}@example.com", hashed_password="x",
                       full_name=f"Mobile {key.upper()}", role="seeker"))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        users = [str(ids.a), str(ids.b)]
        await s.execute(delete(OutboxEvent).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT, OutboxEvent.payload["user_id"].astext.in_(users)))
        await s.execute(delete(User).where(User.id.in_([ids.a, ids.b])))
        await s.commit()


async def _notify(user_id, title="Viewing confirmed", kind="appointment_status_change", link="/appointments"):
    async with AsyncSessionLocal() as s:
        await NotificationService(s).create_notification(user_id, title, "Saturday 11am.", kind,
                                                         reference_id=uuid4(), link=link)


async def _devices(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(DevicePushToken).where(DevicePushToken.user_id == user_id))).scalars().all()


async def _pending(user_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == push_module.PUSH_EVENT, OutboxEvent.status == "pending",
            OutboxEvent.payload["user_id"].astext == str(user_id),
        ))).scalars().all()


# ---------------------------------------------------------------------------- through the API

async def test_devices_register_receive_and_move_between_accounts(async_client, people, apps):
    h = _auth(people.a)
    config = (await async_client.get(f"{API}/notifications/push/config")).json()
    assert config == {"enabled": False, "public_key": None, "native_platforms": ["android", "ios"]}

    url = f"{API}/notifications/push/devices"
    res = await async_client.post(url, json={"platform": "ios", "token": IOS_TOKEN, "app_version": "1.0.0"}, headers=h)
    assert res.status_code == 200 and res.json() == {"registered": True, "devices": 1}
    res = await async_client.post(url, json={"platform": "android", "token": ANDROID_TOKEN}, headers=h)
    assert res.json()["devices"] == 2
    # Registering again (every app start) refreshes, never duplicates.
    assert (await async_client.post(url, json={"platform": "android", "token": ANDROID_TOKEN, "app_version": "1.1"},
                                    headers=h)).json()["devices"] == 2
    # iOS tokens are hex (stored lower-case); anything else is refused before it reaches a URL.
    assert (await async_client.post(url, json={"platform": "ios", "token": "../" + "a" * 64}, headers=h)).status_code == 400
    assert (await async_client.post(url, json={"platform": "ios", "token": ANDROID_TOKEN}, headers=h)).status_code == 400
    assert (await async_client.post(url, json={"platform": "windows", "token": ANDROID_TOKEN}, headers=h)).status_code == 422
    assert (await async_client.post(url, json={"platform": "android", "token": ANDROID_TOKEN, "app_version": "v1"},
                                    headers=h)).status_code == 422
    assert (await async_client.post(url, json={"platform": "android", "token": ANDROID_TOKEN})).status_code == 401
    stored = {d.platform: d for d in await _devices(people.a)}
    assert stored["ios"].token == IOS_TOKEN.lower() and stored["android"].app_version == "1.1"

    await _notify(people.a)
    await dispatch_pending(AsyncSessionLocal)
    assert {(p.platform, p.token) for p in apps.sent} == {("ios", IOS_TOKEN.lower()), ("android", ANDROID_TOKEN)}
    msg = apps.sent[0].message
    assert msg["title"] == "Viewing confirmed" and msg["url"] == "/appointments" and msg["category"] == "rentals"
    assert apps.sent[0].urgency == "normal"

    # The same phone signing in as someone else moves to that account; sign-out removes it.
    assert (await async_client.post(url, json={"platform": "android", "token": ANDROID_TOKEN},
                                    headers=_auth(people.b))).json()["devices"] == 1
    assert [d.platform for d in await _devices(people.a)] == ["ios"]
    # Someone else's token can't be unregistered by another account.
    res = await async_client.post(f"{url}/unregister", json={"token": IOS_TOKEN}, headers=_auth(people.b))
    assert res.json() == {"registered": False, "devices": 1}
    assert len(await _devices(people.a)) == 1
    res = await async_client.post(f"{url}/unregister", json={"token": IOS_TOKEN}, headers=h)
    assert res.json() == {"registered": False, "devices": 0}


async def test_dead_tokens_are_removed_and_temporary_failures_retry_that_device_only(people, apps):
    async with AsyncSessionLocal() as s:
        await NotificationService(s).register_device(people.a, "ios", IOS_TOKEN, "1.0")
        await NotificationService(s).register_device(people.a, "android", ANDROID_TOKEN, "1.0")
        second_android = ANDROID_TOKEN.replace("x", "z")
        await NotificationService(s).register_device(people.a, "android", second_android, "1.0")
    apps.gone.add(ANDROID_TOKEN)
    apps.down.add(IOS_TOKEN.lower())

    await _notify(people.a, "New message from Bilal", "new_message", "/messages")
    await dispatch_pending(AsyncSessionLocal)
    assert [p.token for p in apps.sent] == [second_android]
    assert apps.sent[0].urgency == "high"
    assert {d.token for d in await _devices(people.a)} == {IOS_TOKEN.lower(), second_android}

    [retry] = await _pending(people.a)
    ios = next(d for d in await _devices(people.a) if d.platform == "ios")
    assert retry.payload["device_ids"] == [str(ios.id)] and retry.payload["subscription_ids"] == []
    assert ios.failure_count == 0  # a temporary failure isn't held against the device

    apps.down.clear()
    async with AsyncSessionLocal() as s:
        await s.execute(update(OutboxEvent).where(OutboxEvent.id == retry.id)
                        .values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await s.commit()
    await dispatch_pending(AsyncSessionLocal)
    assert [p.token for p in apps.sent] == [second_android, IOS_TOKEN.lower()]
    assert await _pending(people.a) == []


async def test_a_platform_that_is_off_gets_nothing(people, apps, monkeypatch):
    monkeypatch.setattr(settings, "APNS_PRIVATE_KEY", None)  # iOS push off, Android on
    async with AsyncSessionLocal() as s:
        await NotificationService(s).register_device(people.a, "ios", IOS_TOKEN, None)
        await NotificationService(s).register_device(people.b, "ios", IOS_TOKEN.replace("A", "B"), None)
        await NotificationService(s).register_device(people.b, "android", ANDROID_TOKEN, None)
    await _notify(people.a)  # only an iPhone: nothing to send, nothing queued
    assert await _pending(people.a) == []
    await _notify(people.b)
    await dispatch_pending(AsyncSessionLocal)
    assert [(p.platform, p.token) for p in apps.sent] == [("android", ANDROID_TOKEN)]


async def test_account_export_lists_devices_but_never_tokens(people, apps):
    async with AsyncSessionLocal() as s:
        await NotificationService(s).register_device(people.a, "android", ANDROID_TOKEN, "2.3")
        user = await s.get(User, people.a)
        data = await export_user_data(s, user)
    [device] = data["device_push_tokens"]
    assert device["platform"] == "android" and device["app_version"] == "2.3"
    assert "token" not in device and ANDROID_TOKEN not in json.dumps(data)


# ---------------------------------------------------------------------------- wire format

MESSAGE = {"id": "6f1c", "title": "It's a match!", "body": "Say hello.", "url": "/matches", "category": "matches"}


def test_token_validation():
    assert native_push.normalize_token("ios", " " + IOS_TOKEN + " ") == IOS_TOKEN.lower()
    assert native_push.normalize_token("android", ANDROID_TOKEN) == ANDROID_TOKEN
    for platform, token in (("ios", "zz" * 32), ("ios", "ab" * 10), ("android", "short"),
                            ("android", "a b" * 20), ("android", "x" * 40 + "/../"), ("web", ANDROID_TOKEN)):
        with pytest.raises(BadRequestException):
            native_push.normalize_token(platform, token)


def test_fcm_and_apns_messages(monkeypatch):
    fcm = native_push.fcm_message("tok", MESSAGE, 3600, "high")["message"]
    assert fcm["token"] == "tok" and fcm["notification"] == {"title": "It's a match!", "body": "Say hello."}
    assert fcm["data"] == {"url": "/matches", "id": "6f1c", "category": "matches"}
    assert fcm["android"] == {"priority": "HIGH", "ttl": "3600s", "collapse_key": "6f1c",
                              "notification": {"tag": "6f1c", "channel_id": "matches"}}

    monkeypatch.setattr(settings, "APNS_BUNDLE_ID", "app.flatmate")
    monkeypatch.setattr(settings, "APNS_SANDBOX", True)
    req = native_push.apns_request("ab" * 32, MESSAGE, 60, "normal")
    assert req["url"] == "https://api.sandbox.push.apple.com/3/device/" + "ab" * 32
    assert req["headers"]["apns-topic"] == "app.flatmate" and req["headers"]["apns-priority"] == "5"
    assert req["headers"]["apns-push-type"] == "alert" and req["headers"]["apns-collapse-id"] == "6f1c"
    assert req["json"]["aps"]["alert"] == {"title": "It's a match!", "body": "Say hello."}
    assert req["json"]["url"] == "/matches"
    monkeypatch.setattr(settings, "APNS_SANDBOX", False)
    assert native_push.apns_request("ab" * 32, MESSAGE, 60, "high")["url"].startswith("https://api.push.apple.com/")


class _Response:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


def test_fcm_errors_are_classified(monkeypatch):
    monkeypatch.setattr(native_push, "_google_access_token", lambda: "access")
    calls = []

    def respond(status, body=None, response_headers=None):
        def post(url, json=None, headers=None, timeout=None):
            calls.append((url, headers))
            return _Response(status, body, response_headers)
        monkeypatch.setattr("httpx.post", post)

    monkeypatch.setattr(settings, "FCM_PROJECT_ID", "proj")
    respond(200, {"name": "ok"})
    native_push._send_fcm("tok", MESSAGE, 60, "normal")
    assert calls[-1][0] == "https://fcm.googleapis.com/v1/projects/proj/messages:send"
    assert calls[-1][1]["Authorization"] == "Bearer access"
    for status, body, expected in (
        (404, {"error": {"status": "NOT_FOUND"}}, push_module.PushGone),
        (400, {"error": {"status": "INVALID_ARGUMENT", "details": [{"errorCode": "UNREGISTERED"}]}}, push_module.PushGone),
        (403, {"error": {"status": "PERMISSION_DENIED", "details": [{"errorCode": "SENDER_ID_MISMATCH"}]}}, push_module.PushGone),
        (429, {"error": {"status": "RESOURCE_EXHAUSTED"}}, push_module.PushRetryable),
        (503, None, push_module.PushRetryable),
        (401, {"error": {"status": "UNAUTHENTICATED"}}, push_module.PushRetryable),
        (400, {"error": {"status": "INVALID_ARGUMENT"}}, RuntimeError),
    ):
        respond(status, body, {"Retry-After": "30"})
        with pytest.raises(expected) as exc:
            native_push._send_fcm("tok", MESSAGE, 60, "normal")
        if status == 429:
            assert exc.value.retry_after == 30


def test_apns_errors_are_classified(monkeypatch):
    sent = []

    class Client:
        def __init__(self, status, body):
            self.status, self.body = status, body

        def post(self, url, json=None, headers=None):
            sent.append((url, headers))
            return _Response(self.status, self.body)

    monkeypatch.setattr(native_push, "_apns_provider_token", lambda: "provider")
    monkeypatch.setattr(settings, "APNS_BUNDLE_ID", "app.flatmate")
    for status, body, expected in (
        (200, None, None),
        (410, {"reason": "Unregistered"}, push_module.PushGone),
        (400, {"reason": "BadDeviceToken"}, push_module.PushGone),
        (400, {"reason": "DeviceTokenNotForTopic"}, push_module.PushGone),
        (403, {"reason": "ExpiredProviderToken"}, push_module.PushRetryable),
        (429, {"reason": "TooManyRequests"}, push_module.PushRetryable),
        (503, {"reason": "ServiceUnavailable"}, push_module.PushRetryable),
        (400, {"reason": "PayloadTooLarge"}, RuntimeError),
    ):
        monkeypatch.setattr(native_push, "_apns_http", lambda s=status, b=body: Client(s, b))
        if expected is None:
            native_push._send_apns("ab" * 32, MESSAGE, 60, "high")
        else:
            with pytest.raises(expected):
                native_push._send_apns("ab" * 32, MESSAGE, 60, "high")
    assert sent[0][1]["authorization"] == "bearer provider" and sent[0][1]["apns-priority"] == "10"


def test_credentials_are_signed_and_cached(monkeypatch):
    native_push.reset_credentials()
    # APNs: an ES256 provider token from the .p8 key, reused until it's 50 minutes old.
    ec_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(settings, "APNS_PRIVATE_KEY", _pem(ec_key))
    monkeypatch.setattr(settings, "APNS_KEY_ID", "KEY123")
    monkeypatch.setattr(settings, "APNS_TEAM_ID", "TEAM123")
    token = native_push._apns_provider_token()
    assert jwt.get_unverified_header(token) == {"alg": "ES256", "kid": "KEY123", "typ": "JWT"}
    public = ec_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    assert jwt.decode(token, public.decode(), algorithms=["ES256"])["iss"] == "TEAM123"
    assert native_push._apns_provider_token() == token

    # FCM: an RS256 assertion traded at Google's fixed token endpoint, then cached.
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(settings, "FCM_SERVICE_ACCOUNT_JSON", json.dumps({
        "client_email": "push@proj.iam.gserviceaccount.com", "private_key": _pem(rsa_key),
        "private_key_id": "kid1", "token_uri": "https://attacker.example/token",
    }))
    posts = []

    def post(url, data=None, **kw):
        posts.append(url)
        claims = jwt.decode(data["assertion"], rsa_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
            algorithms=["RS256"], audience=native_push.GOOGLE_TOKEN_URL)
        assert claims["scope"] == native_push.FCM_SCOPE and claims["iss"] == "push@proj.iam.gserviceaccount.com"
        return _Response(200, {"access_token": "ya29.test", "expires_in": 3599})

    monkeypatch.setattr("httpx.post", post)
    assert native_push._google_access_token() == "ya29.test"
    assert native_push._google_access_token() == "ya29.test"
    assert posts == [native_push.GOOGLE_TOKEN_URL]  # never the key file's token_uri, and only once
    native_push.reset_credentials()
