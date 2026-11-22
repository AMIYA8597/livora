"""
Background processing: transactional outbox dispatch (claiming, retries, dead letters,
payload scrubbing, concurrency), maintenance jobs, Celery wiring, image sanitisation.
"""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from PIL import Image
from sqlalchemy import delete, select, text

from app.core.database import AsyncSessionLocal
from app.infrastructure.email import EmailDeliveryError, MemoryEmailProvider, set_email_provider
from app.infrastructure.images import ImageRejected, sanitize_image
from app.modules.messaging.models import OutboxEvent
from app.workers import outbox as outbox_mod
from app.workers.maintenance import run_maintenance
from app.workers.outbox import EMAIL_EVENT, MAX_ATTEMPTS, backoff_for, dispatch_pending
from tests.image_samples import GPS_TAG, make_image


@pytest.fixture
def mailbox():
    provider = MemoryEmailProvider()
    set_email_provider(provider)
    yield provider
    set_email_provider(None)


@pytest.fixture
async def created_ids():
    ids = []
    yield ids
    async with AsyncSessionLocal() as s:
        await s.execute(delete(OutboxEvent).where(OutboxEvent.id.in_(ids)))
        await s.commit()


async def _add_email_event(ids, to=None, retry_count=0, **overrides):
    event = OutboxEvent(
        id=uuid.uuid4(),
        event_type=overrides.pop("event_type", EMAIL_EVENT),
        payload=overrides.pop("payload", None) or {
            "to": to or f"w_{uuid.uuid4().hex[:8]}@example.in",
            "template": "password_reset",
            "context": {"name": "W", "reset_url": "http://localhost:3000/reset-password?token=SECRET", "expires_minutes": 15},
            "idempotency_key": uuid.uuid4().hex,
        },
        status=overrides.pop("status", "pending"),
        retry_count=retry_count,
        **overrides,
    )
    async with AsyncSessionLocal() as s:
        s.add(event)
        await s.commit()
    ids.append(event.id)
    return event


async def _get(event_id):
    async with AsyncSessionLocal() as s:
        return (await s.execute(select(OutboxEvent).where(OutboxEvent.id == event_id))).scalar_one()


# --- Outbox dispatch -----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_delivers_and_scrubs_payload(mailbox, created_ids):
    event = await _add_email_event(created_ids)
    await dispatch_pending(AsyncSessionLocal)

    row = await _get(event.id)
    assert row.status == "published" and row.processed_at is not None
    assert "SECRET" not in str(row.payload)  # reset link scrubbed after delivery
    sent = [m for m in mailbox.outbox if m.to == event.payload["to"]]
    assert len(sent) == 1 and "SECRET" in sent[0].text
    assert sent[0].idempotency_key == event.payload["idempotency_key"]


@pytest.mark.asyncio
async def test_failure_backs_off_then_dead_letters(created_ids):
    class Down(MemoryEmailProvider):
        async def send(self, message):
            raise EmailDeliveryError("provider down")

    set_email_provider(Down())
    try:
        event = await _add_email_event(created_ids)
        before = datetime.now(timezone.utc)
        await dispatch_pending(AsyncSessionLocal)
        row = await _get(event.id)
        assert row.status == "pending" and row.retry_count == 1
        assert "EmailDeliveryError" in (row.last_error or "")
        assert row.next_attempt_at >= before + backoff_for(1) - timedelta(seconds=2)

        # Not due yet: a second sweep leaves it alone.
        await dispatch_pending(AsyncSessionLocal)
        assert (await _get(event.id)).retry_count == 1

        # Final attempt: dead-lettered.
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE outbox_events SET retry_count = :n, next_attempt_at = now() WHERE id = :id"),
                            {"n": MAX_ATTEMPTS - 1, "id": event.id})
            await s.commit()
        await dispatch_pending(AsyncSessionLocal)
        row = await _get(event.id)
        assert row.status == "failed" and row.retry_count == MAX_ATTEMPTS
    finally:
        set_email_provider(None)


@pytest.mark.asyncio
async def test_outage_then_recovery_delivers_exactly_once(created_ids):
    class Flaky(MemoryEmailProvider):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def send(self, message):
            self.calls += 1
            if self.calls == 1:
                raise EmailDeliveryError("blip")
            return await super().send(message)

    provider = Flaky()
    set_email_provider(provider)
    try:
        event = await _add_email_event(created_ids)
        await dispatch_pending(AsyncSessionLocal)
        async with AsyncSessionLocal() as s:
            await s.execute(text("UPDATE outbox_events SET next_attempt_at = now() WHERE id = :id"), {"id": event.id})
            await s.commit()
        await dispatch_pending(AsyncSessionLocal)
        await dispatch_pending(AsyncSessionLocal)
        assert (await _get(event.id)).status == "published"
        assert len([m for m in provider.outbox if m.to == event.payload["to"]]) == 1
    finally:
        set_email_provider(None)


@pytest.mark.asyncio
async def test_concurrent_dispatchers_never_double_send(created_ids, monkeypatch):
    sends = []

    async def slow_handler(payload):
        sends.append(payload["idempotency_key"])
        await asyncio.sleep(0.05)
        return {"scrubbed": True}

    monkeypatch.setitem(outbox_mod.HANDLERS, EMAIL_EVENT, slow_handler)
    events = [await _add_email_event(created_ids) for _ in range(12)]
    await asyncio.gather(*(dispatch_pending(AsyncSessionLocal, batch_size=5) for _ in range(4)))
    await dispatch_pending(AsyncSessionLocal)

    mine = {e.payload["idempotency_key"] for e in events}
    delivered = [k for k in sends if k in mine]
    assert sorted(delivered) == sorted(mine)  # each exactly once


@pytest.mark.asyncio
async def test_unknown_event_type_is_retried_not_dropped(mailbox, created_ids):
    event = await _add_email_event(created_ids, event_type="mystery.event", payload={"x": 1})
    await dispatch_pending(AsyncSessionLocal)
    row = await _get(event.id)
    assert row.status == "pending" and row.retry_count == 1
    assert "No outbox handler" in row.last_error


@pytest.mark.asyncio
async def test_message_created_events_are_consumed_without_message_text(mailbox, created_ids):
    event = await _add_email_event(created_ids, event_type="message.created", payload={
        "id": str(uuid.uuid4()), "conversation_id": str(uuid.uuid4()), "sender_id": str(uuid.uuid4()),
        "content": "my address is 12 Secret Lane", "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    await dispatch_pending(AsyncSessionLocal)
    row = await _get(event.id)
    assert row.status == "published"
    assert "Secret Lane" not in str(row.payload)


def test_backoff_is_exponential_and_capped():
    assert backoff_for(1) == timedelta(seconds=30)
    assert backoff_for(2) == timedelta(seconds=60)
    assert backoff_for(20) == timedelta(hours=1)


# --- Maintenance ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_maintenance_purges_and_expires(created_ids):
    from geoalchemy2.elements import WKTElement
    from app.modules.appointments.models import Appointment
    from app.modules.properties.models import Property
    from app.modules.subscriptions.models import Subscription, SubscriptionPlan
    from app.modules.users.models import User

    old = datetime.now(timezone.utc) - timedelta(days=40)
    stale_published = await _add_email_event(created_ids, status="published", processed_at=old)
    stale_failed = await _add_email_event(created_ids, status="failed", processed_at=old)
    fresh_published = await _add_email_event(created_ids, status="published", processed_at=datetime.now(timezone.utc))

    host_id, guest_id, plan_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add_all([
            User(id=host_id, email=f"h_{host_id.hex[:8]}@example.in", hashed_password="x", full_name="Host"),
            User(id=guest_id, email=f"g_{guest_id.hex[:8]}@example.in", hashed_password="x", full_name="Guest"),
        ])
        await s.flush()
        prop = Property(
            id=uuid.uuid4(), owner_id=host_id, title="T", description="d",
            location=WKTElement("POINT(77.6 12.9)", srid=4326), address_display="a", address_exact="b",
            city="Bengaluru", postal_code="560001", monthly_rent=Decimal("1000"),
            available_from=datetime.now(timezone.utc).date(),
        )
        s.add(prop)
        await s.flush()
        stale_appt = Appointment(property_id=prop.id, host_id=host_id, applicant_id=guest_id, status="pending",
                                 scheduled_at=datetime.now(timezone.utc) - timedelta(days=3))
        future_appt = Appointment(property_id=prop.id, host_id=host_id, applicant_id=guest_id, status="pending",
                                  scheduled_at=datetime.now(timezone.utc) + timedelta(days=3))
        s.add_all([stale_appt, future_appt])
        s.add(SubscriptionPlan(id=plan_id, name="Test plan", code=f"p{plan_id.hex[:10]}", price_inr=Decimal("99")))
        await s.flush()
        sub = Subscription(user_id=guest_id, plan_id=plan_id, status="active",
                           expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        s.add(sub)
        await s.commit()
        ids = (stale_appt.id, future_appt.id, sub.id)

    try:
        counts = await run_maintenance(AsyncSessionLocal)
        assert counts["purge_published_outbox"] >= 1 and counts["purge_failed_outbox"] >= 1
        async with AsyncSessionLocal() as s:
            remaining = set((await s.execute(select(OutboxEvent.id).where(OutboxEvent.id.in_(
                [stale_published.id, stale_failed.id, fresh_published.id])))).scalars())
            assert remaining == {fresh_published.id}
            statuses = dict((await s.execute(select(Appointment.id, Appointment.status).where(
                Appointment.id.in_(ids[:2])))).all())
            assert statuses == {ids[0]: "cancelled", ids[1]: "pending"}
            assert (await s.execute(select(Subscription.status).where(Subscription.id == ids[2]))).scalar_one() == "expired"
        # Idempotent: a second run changes nothing it already handled.
        again = await run_maintenance(AsyncSessionLocal)
        assert again["expire_subscriptions"] == 0 and again["expire_unconfirmed_appointments"] == 0
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(User).where(User.id.in_([host_id, guest_id])))
            await s.execute(delete(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
            await s.commit()


# --- Celery wiring -------------------------------------------------------------------------

def test_celery_tasks_and_schedule_registered():
    from app.workers import tasks  # noqa: F401 - registers tasks
    from app.workers.celery_app import celery_app

    assert {"outbox.dispatch", "maintenance.run"} <= set(celery_app.tasks.keys())
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled == {"outbox.dispatch", "maintenance.run"}
    assert celery_app.conf.task_acks_late is True


def test_celery_task_runs_with_its_own_event_loop(mailbox):
    """The task body works outside the app's loop (fresh NullPool engine per run)."""
    from app.workers.tasks import dispatch_outbox
    result = dispatch_outbox.run()
    assert set(result) == {"claimed", "published", "retried", "dead_lettered"}


# --- Image sanitisation --------------------------------------------------------------------

def test_gps_metadata_is_stripped():
    original = make_image("JPEG", with_gps=True)
    assert Image.open(io.BytesIO(original)).getexif().get_ifd(GPS_TAG)  # precondition
    cleaned = sanitize_image(original, "image/jpeg")
    exif = Image.open(io.BytesIO(cleaned)).getexif()
    assert not exif.get_ifd(GPS_TAG) and 0x010F not in exif


def test_orientation_is_applied_to_pixels():
    img = Image.new("RGB", (40, 20), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    cleaned = Image.open(io.BytesIO(sanitize_image(buf.getvalue(), "image/jpeg")))
    assert cleaned.size == (20, 40)
    assert 0x0112 not in cleaned.getexif()


@pytest.mark.parametrize("fmt,ctype", [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_png_and_webp_roundtrip(fmt, ctype):
    cleaned = sanitize_image(make_image(fmt), ctype)
    assert Image.open(io.BytesIO(cleaned)).format == fmt


def test_declared_type_must_match_content():
    with pytest.raises(ImageRejected):
        sanitize_image(make_image("PNG"), "image/jpeg")


def test_truncated_or_fake_image_rejected():
    with pytest.raises(ImageRejected):
        sanitize_image(b"\xff\xd8\xff\xe0" + b"\x00" * 64, "image/jpeg")


def test_decompression_bomb_rejected():
    big = Image.new("1", (9000, 9000))  # 81 MP, tiny on disk
    buf = io.BytesIO()
    big.save(buf, "PNG")
    with pytest.raises(ImageRejected):
        sanitize_image(buf.getvalue(), "image/png")


def test_trailing_payload_is_dropped():
    polyglot = make_image("JPEG") + b"<script>alert(1)</script>"
    assert b"<script>" not in sanitize_image(polyglot, "image/jpeg")
