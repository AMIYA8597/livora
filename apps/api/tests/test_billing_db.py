"""
Payments against a real database with a fake Razorpay (httpx MockTransport): billing off/on,
free-tier caps, checkout and signature verification, webhooks (signature, idempotency,
ordering, renewals), cancellation, featured listings and "who liked you".
"""
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.modules.billing import service as billing_service
from app.modules.billing.razorpay import RazorpayClient, verify_webhook_signature
from app.modules.matching.models import MatchInteraction
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.subscriptions.models import BillingEvent, Payment, Subscription, SubscriptionPlan
from app.modules.users.models import User, UserPrivacySetting
from app.workers.maintenance import run_maintenance

API = settings.API_V1_PREFIX
KEY_SECRET = "test_key_secret"
WEBHOOK_SECRET = "test_webhook_secret"


def _auth(user_id, role="seeker") -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


def _sign(payment_id: str, subscription_id: str) -> str:
    return hmac.new(KEY_SECRET.encode(), f"{payment_id}|{subscription_id}".encode(), hashlib.sha256).hexdigest()


class FakeRazorpay:
    """Just enough of the Razorpay API, with call counts."""

    def __init__(self):
        self.plans_created = 0
        self.subscriptions = {}
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")  # key id + secret
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        body = json.loads(request.content or b"{}")
        if method == "POST" and path == "/v1/plans":
            self.plans_created += 1
            assert body["item"]["currency"] == "INR" and body["item"]["amount"] > 0
            return httpx.Response(200, json={"id": f"plan_Fake{self.plans_created:06d}", "item": body["item"]})
        if method == "POST" and path == "/v1/subscriptions":
            sid = f"sub_Fake{uuid4().hex[:12]}"
            self.subscriptions[sid] = {"id": sid, "status": "created", "plan_id": body["plan_id"],
                                       "short_url": f"https://rzp.io/i/{sid}"}
            return httpx.Response(200, json=self.subscriptions[sid])
        if path.startswith("/v1/subscriptions/"):
            sid = path.split("/")[3]
            if sid not in self.subscriptions:
                return httpx.Response(400, json={"error": {"description": "The id provided does not exist"}})
            if method == "GET":
                return httpx.Response(200, json=self.subscriptions[sid])
            if path.endswith("/cancel"):
                entity = self.subscriptions[sid]
                if not body.get("cancel_at_cycle_end"):
                    entity["status"] = "cancelled"
                return httpx.Response(200, json=entity)
        return httpx.Response(404, json={"error": {"description": "unknown"}})

    def pay(self, sid: str, days: int = 30):
        now = int(time.time())
        self.subscriptions[sid].update(status="active", current_start=now, current_end=now + days * 86400)


@pytest.fixture
def fake_rzp(monkeypatch):
    fake = FakeRazorpay()
    transport = httpx.MockTransport(fake.handler)
    monkeypatch.setattr(billing_service, "RazorpayClient", lambda: RazorpayClient(transport=transport))
    return fake


@pytest.fixture
def billing_on(monkeypatch, fake_rzp):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", KEY_SECRET)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "FREE_DAILY_LIKES", 2)
    monkeypatch.setattr(settings, "FREE_ACTIVE_LISTINGS", 1)
    return fake_rzp


@pytest.fixture
async def people():
    """A seeker, two admirers (one with a private profile), an owner, and a unique city."""
    ids = SimpleNamespace(seeker=uuid4(), fan=uuid4(), shy_fan=uuid4(), owner=uuid4(), city=f"Paypur{uuid4().hex[:6]}")
    async with AsyncSessionLocal() as s:
        for key, role in (("seeker", "seeker"), ("fan", "seeker"), ("shy_fan", "seeker"), ("owner", "owner")):
            s.add(User(id=getattr(ids, key), email=f"bill-{key}-{uuid4().hex[:6]}@example.com",
                       hashed_password="x", full_name=key.title(), role=role))
        await s.flush()
        s.add(UserPrivacySetting(user_id=ids.shy_fan, profile_visibility="private"))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        users = [ids.seeker, ids.fan, ids.shy_fan, ids.owner]
        sub_ids = select(Subscription.id).where(Subscription.user_id.in_(users))
        await s.execute(delete(Payment).where(Payment.user_id.in_(users)))
        await s.execute(delete(BillingEvent).where(BillingEvent.payload["payload"]["subscription"]["entity"]["id"].astext.in_(
            select(Subscription.provider_subscription_id).where(Subscription.user_id.in_(users)))))
        await s.execute(delete(Subscription).where(Subscription.id.in_(sub_ids)))
        await s.execute(delete(User).where(User.id.in_(users)))
        await s.commit()


def _listing(owner_id, city, title, status="published"):
    return Property(
        id=uuid4(), owner_id=owner_id, title=title, description="Bright and airy.",
        location=WKTElement("POINT(77.6 12.9)", srid=4326), address_display=f"Koramangala, {city}",
        address_exact="1 Pay St", city=city, postal_code="560034", monthly_rent=Decimal("20000"),
        available_from=date.today(), listing_status=status, is_active=True,
    )


def _event(event_type, sid, *, status="active", created_at=None, current_end=None, payment=None):
    now = int(time.time())
    payload = {"subscription": {"entity": {"id": sid, "status": status, "current_start": now,
                                           "current_end": current_end or now + 30 * 86400}}}
    if payment:
        payload["payment"] = {"entity": payment}
    return {"entity": "event", "event": event_type, "created_at": created_at or now, "payload": payload}


async def _webhook(client, event, *, event_id=None, secret=WEBHOOK_SECRET):
    raw = json.dumps(event).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return await client.post(f"{API}/billing/webhooks/razorpay", content=raw, headers={
        "X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id or f"evt_{uuid4().hex[:14]}",
        "Content-Type": "application/json"})


async def _subscribe(client, fake, user_id, plan_code):
    """Checkout + payment + verify, as the browser would."""
    res = await client.post(f"{API}/billing/subscriptions", json={"plan_code": plan_code}, headers=_auth(user_id))
    assert res.status_code == 200, res.text
    sid = res.json()["subscription_id"]
    fake.pay(sid)
    pay_id = f"pay_Fake{uuid4().hex[:12]}"
    res = await client.post(f"{API}/billing/subscriptions/verify", headers=_auth(user_id), json={
        "razorpay_payment_id": pay_id, "razorpay_subscription_id": sid, "razorpay_signature": _sign(pay_id, sid)})
    assert res.status_code == 200, res.text
    return sid


# ============================================================================ billing off


@pytest.mark.asyncio
async def test_without_keys_nothing_is_limited_and_paid_features_are_hidden(async_client, people, fake_rzp):
    plans = (await async_client.get(f"{API}/billing/plans")).json()
    assert plans["enabled"] is False and {p["code"] for p in plans["plans"]} >= {"seeker_pro", "owner_pro"}

    me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
    assert me["entitlements"]["daily_likes"] is None and me["entitlements"]["max_active_listings"] is None
    assert me["entitlements"]["who_liked_me"] is False

    res = await async_client.post(f"{API}/billing/subscriptions", json={"plan_code": "seeker_pro"},
                                  headers=_auth(people.seeker))
    assert res.status_code == 503 and res.json()["error_code"] == "BILLING_DISABLED"
    assert fake_rzp.calls == []

    # Webhooks are refused without a secret.
    res = await _webhook(async_client, _event("subscription.charged", "sub_Nope000000"))
    assert res.status_code == 401


# ============================================================================ free tier


@pytest.mark.asyncio
async def test_free_tier_daily_like_cap(async_client, people, billing_on):
    async with AsyncSessionLocal() as s:
        targets = [uuid4() for _ in range(3)]
        for t in targets:
            s.add(User(id=t, email=f"t-{t.hex[:8]}@example.com", hashed_password="x", full_name="T"))
        await s.commit()
    try:
        like = lambda t, action="like": async_client.post(  # noqa: E731
            f"{API}/matching/interactions", json={"target_user_id": str(t), "action": action},
            headers=_auth(people.seeker))
        assert (await like(targets[0])).status_code == 200
        assert (await like(targets[1])).status_code == 200
        assert (await like(targets[0])).status_code == 200  # re-liking doesn't use the allowance
        third = await like(targets[2])
        assert third.status_code == 402
        assert third.json()["error_code"] == "UPGRADE_REQUIRED" and third.json()["plan"] == "seeker_pro"
        assert (await like(targets[2], "pass")).status_code == 200  # passing is always free

        me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
        assert me["usage"]["likes_today"] == 2 and me["entitlements"]["daily_likes"] == 2

        await _subscribe(async_client, billing_on, people.seeker, "seeker_pro")
        assert (await like(targets[2])).status_code == 200  # Seeker Pro: no cap
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(MatchInteraction).where(MatchInteraction.user_id == people.seeker))
            await s.execute(delete(User).where(User.id.in_(targets)))
            await s.commit()


@pytest.mark.asyncio
async def test_free_tier_listing_cap_and_owner_pro(async_client, people, billing_on):
    first = _listing(people.owner, people.city, "First flat")
    paused = _listing(people.owner, people.city, "Paused flat", status="paused")
    async with AsyncSessionLocal() as s:
        s.add_all([first, paused])
        await s.commit()
    publish = lambda pid: async_client.patch(  # noqa: E731
        f"{API}/properties/{pid}/status", json={"listing_status": "published"}, headers=_auth(people.owner, "owner"))

    res = await publish(paused.id)
    assert res.status_code == 402 and res.json()["plan"] == "owner_pro"

    # Creating a listing (published at once) is capped the same way.
    async with AsyncSessionLocal() as s:
        with pytest.raises(Exception) as err:
            await PropertyService(s).create(people.owner, PropertyCreate(
                title="Third flat", description="d", property_category="apartment", configuration="1BHK",
                latitude=12.93, longitude=77.62, address_display="Koramangala", address_exact="x",
                city=people.city, state="Karnataka", postal_code="560034", monthly_rent=Decimal("15000"),
                max_capacity=1, available_from=date.today(), currency="INR"))
        assert getattr(err.value, "status_code", None) == 402

    # Pausing the first frees the slot.
    res = await async_client.patch(f"{API}/properties/{first.id}/status", json={"listing_status": "paused"},
                                   headers=_auth(people.owner, "owner"))
    assert res.status_code == 200
    assert (await publish(paused.id)).status_code == 200
    assert (await publish(first.id)).status_code == 402

    await _subscribe(async_client, billing_on, people.owner, "owner_pro")
    assert (await publish(first.id)).status_code == 200


# ============================================================================ checkout


@pytest.mark.asyncio
async def test_checkout_creates_plan_once_reuses_open_checkout_and_verifies_signature(async_client, people, billing_on):
    async with AsyncSessionLocal() as s:  # a fresh Razorpay plan for this test
        await s.execute(update(SubscriptionPlan).where(SubscriptionPlan.code == "seeker_pro")
                        .values(razorpay_plan_id=None, razorpay_plan_amount=None))
        await s.commit()

    start = lambda uid: async_client.post(  # noqa: E731
        f"{API}/billing/subscriptions", json={"plan_code": "seeker_pro"}, headers=_auth(uid))
    a1, a2, b1 = (await start(people.seeker)).json(), (await start(people.seeker)).json(), (await start(people.fan)).json()
    assert a1["subscription_id"] == a2["subscription_id"]  # unfinished checkout reused
    assert b1["subscription_id"] != a1["subscription_id"]
    assert billing_on.plans_created == 1  # the Razorpay plan is created once and stored
    assert a1["key_id"] == "rzp_test_fake" and a1["amount_inr"] == "199.00"
    assert (await async_client.post(f"{API}/billing/subscriptions", json={"plan_code": "nope"},
                                    headers=_auth(people.seeker))).status_code == 404

    sid = a1["subscription_id"]
    billing_on.pay(sid)
    pay_id = "pay_Fake123456789"
    verify = lambda sig, uid=people.seeker: async_client.post(  # noqa: E731
        f"{API}/billing/subscriptions/verify", headers=_auth(uid),
        json={"razorpay_payment_id": pay_id, "razorpay_subscription_id": sid, "razorpay_signature": sig})
    assert (await verify("0" * 64)).status_code == 400  # forged
    assert (await verify(_sign(pay_id, sid), people.fan)).status_code == 404  # someone else's
    res = await verify(_sign(pay_id, sid))
    assert res.status_code == 200 and res.json()["status"] == "active"

    me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
    assert me["entitlements"]["who_liked_me"] and me["entitlements"]["plans"] == ["seeker_pro"]
    assert me["subscriptions"][0]["renews"] is True
    again = await start(people.seeker)
    assert again.status_code == 409 and again.json()["error_code"] == "ALREADY_SUBSCRIBED"


# ============================================================================ webhooks


@pytest.mark.asyncio
async def test_webhooks_are_verified_idempotent_ordered_and_extend_the_period(async_client, people, billing_on):
    sid = await _subscribe(async_client, billing_on, people.seeker, "seeker_pro")
    async with AsyncSessionLocal() as s:
        first_end = (await s.execute(select(Subscription.expires_at).where(
            Subscription.provider_subscription_id == sid))).scalar_one()

    later = int(time.time()) + 60 * 86400
    charged = _event("subscription.charged", sid, current_end=later, payment={
        "id": "pay_Renewal0000001", "amount": 19900, "currency": "INR", "status": "captured", "method": "upi",
        "created_at": int(time.time())})
    assert (await _webhook(async_client, charged, secret="wrong")).status_code == 401
    res = await _webhook(async_client, charged, event_id="evt_charged_1")
    assert res.status_code == 200 and res.json()["status"] == "processed"
    assert (await _webhook(async_client, charged, event_id="evt_charged_1")).json()["status"] == "duplicate"

    async with AsyncSessionLocal() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.provider_subscription_id == sid))).scalar_one()
        assert sub.expires_at > first_end and int(sub.expires_at.timestamp()) == later
        pays = (await s.execute(select(Payment).where(Payment.gateway_payment_id == "pay_Renewal0000001"))).scalars().all()
        assert len(pays) == 1 and pays[0].status == "successful" and pays[0].amount == Decimal("199.00")
        assert pays[0].method == "upi"

    # A late, older event can't roll the subscription back.
    stale = _event("subscription.halted", sid, status="halted", created_at=int(time.time()) - 3600,
                   current_end=int(time.time()) - 3600)
    assert (await _webhook(async_client, stale)).json()["status"] == "processed"
    async with AsyncSessionLocal() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.provider_subscription_id == sid))).scalar_one()
        assert sub.status == "active" and int(sub.expires_at.timestamp()) == later

    # Unknown subscriptions and other events are acknowledged and ignored.
    assert (await _webhook(async_client, _event("subscription.charged", "sub_NotOurs00001"))).json()["status"] == "ignored"
    assert (await _webhook(async_client, {"event": "payment.captured", "payload": {}, "created_at": 1})).json()["status"] == "ignored"

    # A newer halt applies; access lasts until the paid period ends, then stops.
    halt_at = int(time.time()) + 10
    await _webhook(async_client, _event("subscription.halted", sid, status="halted", created_at=halt_at,
                                        current_end=int(time.time()) - 1))
    me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
    assert me["entitlements"]["who_liked_me"] is False


def test_webhook_signature_check_is_exact():
    body = b'{"event":"subscription.charged"}'
    good = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(body, good, secret="s3cret")
    assert not verify_webhook_signature(body + b" ", good, secret="s3cret")
    assert not verify_webhook_signature(body, good, secret="")
    assert not verify_webhook_signature(body, None, secret="s3cret")


@pytest.mark.asyncio
async def test_cancel_keeps_the_paid_period_and_maintenance_leaves_live_plans_alone(async_client, people, billing_on):
    sid = await _subscribe(async_client, billing_on, people.seeker, "seeker_pro")
    me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
    sub_id = me["subscriptions"][0]["id"]
    assert (await async_client.post(f"{API}/billing/subscriptions/{sub_id}/cancel",
                                    headers=_auth(people.fan))).status_code == 404
    res = await async_client.post(f"{API}/billing/subscriptions/{sub_id}/cancel", headers=_auth(people.seeker))
    assert res.status_code == 200 and res.json()["cancel_at_period_end"] is True
    assert ("POST", f"/v1/subscriptions/{sid}/cancel") in billing_on.calls

    me = (await async_client.get(f"{API}/billing/me", headers=_auth(people.seeker))).json()
    assert me["entitlements"]["who_liked_me"] is True  # paid until the period ends
    assert me["subscriptions"][0]["renews"] is False

    # An "active" Razorpay subscription whose period just ended is awaiting its renewal webhook:
    # maintenance must not expire it.
    async with AsyncSessionLocal() as s:
        await s.execute(update(Subscription).where(Subscription.provider_subscription_id == sid)
                        .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        await s.commit()
    await run_maintenance(AsyncSessionLocal)
    async with AsyncSessionLocal() as s:
        assert (await s.execute(select(Subscription.status).where(
            Subscription.provider_subscription_id == sid))).scalar_one() == "active"


# ============================================================================ paid features


@pytest.mark.asyncio
async def test_featured_listings_need_owner_pro_rank_first_and_follow_renewals(async_client, people, billing_on):
    props = [_listing(people.owner, people.city, f"Flat {i}") for i in range(5)]
    async with AsyncSessionLocal() as s:
        s.add_all(props)
        await s.commit()
    owner = _auth(people.owner, "owner")
    feature = lambda p: async_client.post(f"{API}/properties/{p.id}/feature", headers=owner)  # noqa: E731

    res = await feature(props[0])
    assert res.status_code == 402 and res.json()["feature"] == "featured_listings"

    sid = await _subscribe(async_client, billing_on, people.owner, "owner_pro")
    assert (await async_client.post(f"{API}/properties/{props[0].id}/feature",
                                    headers=_auth(people.seeker))).status_code == 403
    oldest = props[0]  # created first, so last in "newest" order unless featured
    res = await feature(oldest)
    assert res.status_code == 200 and res.json()["is_featured"] is True
    listed = (await async_client.get(f"{API}/properties", params={"city": people.city})).json()
    assert listed[0]["id"] == str(oldest.id) and listed[0]["is_featured"]

    for p in props[1:3]:
        assert (await feature(p)).status_code == 200
    over = await feature(props[3])
    assert over.status_code == 402 and over.json()["error_code"] == "FEATURED_LIMIT"

    # A renewal keeps featured listings featured for the new period.
    later = int(time.time()) + 90 * 86400
    await _webhook(async_client, _event("subscription.charged", sid, current_end=later))
    async with AsyncSessionLocal() as s:
        until = (await s.execute(select(Property.featured_until).where(Property.id == oldest.id))).scalar_one()
        assert int(until.timestamp()) == later

    # Unpublishing frees the slot.
    await async_client.patch(f"{API}/properties/{oldest.id}/status", json={"listing_status": "paused"}, headers=owner)
    assert (await feature(props[3])).status_code == 200
    assert (await async_client.delete(f"{API}/properties/{props[3].id}/feature", headers=owner)).json()["is_featured"] is False


@pytest.mark.asyncio
async def test_who_liked_you_is_counted_for_everyone_and_named_for_seeker_pro(async_client, people, billing_on):
    async with AsyncSessionLocal() as s:
        s.add_all([MatchInteraction(user_id=people.fan, target_user_id=people.seeker, action="super_like"),
                   MatchInteraction(user_id=people.shy_fan, target_user_id=people.seeker, action="like")])
        await s.commit()
    try:
        res = (await async_client.get(f"{API}/matching/likes-received", headers=_auth(people.seeker))).json()
        assert res == {"count": 2, "locked": True, "people": [], "hidden": 2, "upgrade_available": True}

        await _subscribe(async_client, billing_on, people.seeker, "seeker_pro")
        res = (await async_client.get(f"{API}/matching/likes-received", headers=_auth(people.seeker))).json()
        assert res["count"] == 2 and res["locked"] is False and res["hidden"] == 1  # private profile stays hidden
        assert [p["user_id"] for p in res["people"]] == [str(people.fan)] and res["people"][0]["super_like"]

        # Answering removes them from the list.
        await async_client.post(f"{API}/matching/interactions", headers=_auth(people.seeker),
                                json={"target_user_id": str(people.fan), "action": "pass"})
        res = (await async_client.get(f"{API}/matching/likes-received", headers=_auth(people.seeker))).json()
        assert res["count"] == 1 and res["people"] == []
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(MatchInteraction).where(MatchInteraction.target_user_id == people.seeker))
            await s.execute(delete(MatchInteraction).where(MatchInteraction.user_id == people.seeker))
            await s.commit()
