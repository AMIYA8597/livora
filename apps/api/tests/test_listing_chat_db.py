"""
"Ask the owner" listing chats against a real database: who can open one, reuse, contact details
hidden until the owner confirms a visit (and staying visible after), the visit state rule that
protects that, and the owner's response-time badge.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from app.core import rate_limit
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestException
from app.core.security import create_access_token
from app.modules.appointments.models import Appointment
from app.modules.appointments.schemas import AppointmentStatusUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.messaging.contact_guard import HIDDEN, VISIT_CONFIRMED_NOTE, hide_contacts
from app.modules.messaging.models import Conversation, ConversationParticipant, Message, OutboxEvent
from app.modules.messaging.response_time import MIN_CHATS, owner_response, response_label
from app.modules.notifications.models import Notification
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.users.models import User

API = settings.API_V1_PREFIX
PHONE = "98765 43210"


def auth(user_id, role="seeker"):
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=[role])}"}


# ---------------------------------------------------------------- pure parts

@pytest.mark.parametrize("text", [
    "call me on 9876543210", "+91 98765 43210", "+91-98765-43210", "098765 43210",
    "my number is (98) 7654-3210.", "mail asha.k+rooms@gmail.com",
])
def test_contacts_are_hidden(text):
    shown, hidden = hide_contacts(text)
    assert hidden and HIDDEN in shown
    assert "43210" not in shown and "gmail" not in shown


@pytest.mark.parametrize("text", [
    "Rent 15000, deposit 30000", "Visit on 24/11/2026 at 10", "Flat 1234567890",
    "pay to raj@okaxis",  # a UPI id is a payment handle: the scam pre-screen warns about it
    "Room 7 on floor 3, 2 baths",
])
def test_ordinary_text_is_left_alone(text):
    assert hide_contacts(text) == (text, False)


def test_response_labels():
    assert response_label(1.0, 20) == "Usually replies within an hour"
    assert response_label(0.9, 150) == "Usually replies within a few hours"
    assert response_label(0.8, 600) == "Usually replies within a day"
    assert response_label(0.8, 3000) == "Usually replies within a few days"
    assert response_label(0.4, 10) == "Often slow to reply"


# ---------------------------------------------------------------- a listing, its owner, seekers

@pytest.fixture
async def listing():
    tag = f"Ask{uuid4().hex[:8]}"
    owner, seeker, other = uuid4(), uuid4(), uuid4()
    async with AsyncSessionLocal() as s:
        s.add_all([
            User(id=owner, email=f"{tag}-o@example.com", hashed_password="x", full_name="Olu Owner", role="owner"),
            User(id=seeker, email=f"{tag}-s@example.com", hashed_password="x", full_name="Sia Seeker", role="seeker"),
            User(id=other, email=f"{tag}-x@example.com", hashed_password="x", full_name="Xan Stranger", role="seeker"),
        ])
        await s.commit()
    async with AsyncSessionLocal() as s:
        pid = (await PropertyService(s).create(owner, PropertyCreate(
            title=f"{tag} room", description="Room.", property_category="apartment", configuration="1BHK",
            latitude=25.6751, longitude=94.1086, address_display=f"{tag} Colony, Kohima",
            address_exact="1 Test Road", city="Kohima", state="Nagaland", postal_code="797001",
            monthly_rent=Decimal("12000"), max_capacity=2, available_from=date.today(), currency="INR",
        )))["id"]
    await rate_limit.reset()

    yield SimpleNamespace(owner=owner, seeker=seeker, other=other, property_id=pid)

    async with AsyncSessionLocal() as s:
        users = [owner, seeker, other]
        convs = select(ConversationParticipant.conversation_id).where(ConversationParticipant.user_id.in_(users))
        conv_ids = [str(c) for c in (await s.execute(convs)).scalars().all()]
        await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["conversation_id"].astext.in_(conv_ids)))
        await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["property_id"].astext == str(pid)))
        # Listing creation also queues an embedding refresh, keyed by entity_id.
        await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["entity_id"].astext == str(pid)))
        await s.execute(delete(Notification).where(Notification.user_id.in_(users)))
        await s.execute(delete(Conversation).where(Conversation.id.in_(convs)))
        await s.execute(delete(Appointment).where(Appointment.property_id == pid))
        await s.execute(delete(Property).where(Property.id == pid))
        await s.execute(delete(User).where(User.id.in_(users)))
        await s.commit()


async def _ask(client, user, property_id, content=""):
    return await client.post(f"{API}/messaging/listing-chats", headers=auth(user),
                             json={"property_id": str(property_id), "content": content})


async def _messages(client, user, conv_id):
    res = await client.get(f"{API}/messaging/conversations/{conv_id}/messages", headers=auth(user))
    assert res.status_code == 200, res.text
    return res.json()


async def test_ask_the_owner_opens_one_chat_per_listing(async_client, listing):
    first = await _ask(async_client, listing.seeker, listing.property_id, "Is the deposit refundable?")
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["created"] is True and body["message_id"]

    again = (await _ask(async_client, listing.seeker, listing.property_id, "And are visitors allowed?")).json()
    assert again["conversation_id"] == body["conversation_id"] and again["created"] is False

    async with AsyncSessionLocal() as s:
        conv = await s.get(Conversation, body["conversation_id"])
        assert conv.type == "property_inquiry" and conv.property_id == listing.property_id
        members = set((await s.execute(select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conv.id))).scalars().all())
        assert members == {listing.owner, listing.seeker}

    texts = [m["content"] for m in await _messages(async_client, listing.owner, body["conversation_id"])]
    assert texts == ["Is the deposit refundable?", "And are visitors allowed?"]


async def test_who_can_ask(async_client, listing):
    own = await _ask(async_client, listing.owner, listing.property_id, "hi")
    assert own.status_code == 400
    missing = await _ask(async_client, listing.seeker, uuid4(), "hi")
    assert missing.status_code == 404
    async with AsyncSessionLocal() as s:
        await s.execute(update(Property).where(Property.id == listing.property_id).values(is_active=False))
        await s.commit()
    inactive = await _ask(async_client, listing.seeker, listing.property_id, "hi")
    assert inactive.status_code == 404


async def test_a_listing_chat_must_include_the_owner(async_client, listing):
    """The generic endpoint can't be used to open a 'listing chat' with a stranger."""
    res = await async_client.post(f"{API}/messaging/conversations", headers=auth(listing.seeker), json={
        "participant_user_ids": [str(listing.other)], "type": "property_inquiry",
        "property_id": str(listing.property_id),
    })
    assert res.status_code == 400
    ok = await async_client.post(f"{API}/messaging/conversations", headers=auth(listing.seeker), json={
        "participant_user_ids": [str(listing.owner)], "type": "property_inquiry",
        "property_id": str(listing.property_id),
    })
    assert ok.status_code == 201, ok.text


async def test_contacts_hidden_until_the_owner_confirms_a_visit(async_client, listing):
    asked = (await _ask(async_client, listing.seeker, listing.property_id, f"Call me on {PHONE}")).json()
    conv_id = asked["conversation_id"]

    # Hidden for both people, everywhere the text appears.
    for user in (listing.owner, listing.seeker):
        [msg] = await _messages(async_client, user, conv_id)
        assert PHONE not in msg["content"] and msg["contact_hidden"] is True
        inbox = (await async_client.get(f"{API}/messaging/conversations", headers=auth(user))).json()
        last = next(c for c in inbox if c["id"] == conv_id)["last_message"]
        assert PHONE not in last["content"] and last["contact_hidden"] is True
    searched = (await async_client.get(f"{API}/messaging/conversations", params={"q": "43210"},
                                       headers=auth(listing.owner))).json()
    assert all(c["id"] != conv_id for c in searched)  # searching can't probe a hidden number

    sent = await async_client.post(f"{API}/messaging/messages", headers=auth(listing.owner),
                                   json={"conversation_id": conv_id, "content": "Mail me at olu@example.org"})
    assert sent.status_code == 201 and "example.org" not in sent.json()["content"]

    # The seeker can't unlock it: a visit can't be "completed" without the owner confirming it.
    async with AsyncSessionLocal() as s:
        appt = Appointment(property_id=listing.property_id, host_id=listing.owner, applicant_id=listing.seeker,
                           scheduled_at=datetime.now(timezone.utc) + timedelta(days=2))
        s.add(appt)
        await s.commit()
        appt_id = appt.id
    async with AsyncSessionLocal() as s:
        with pytest.raises(BadRequestException):
            await AppointmentService(s).update_status(appt_id, listing.seeker, AppointmentStatusUpdate(status="completed"))
    [still_hidden, _] = await _messages(async_client, listing.seeker, conv_id)
    assert PHONE not in still_hidden["content"]

    # The owner confirms: everything shows, with a note in the chat.
    async with AsyncSessionLocal() as s:
        await AppointmentService(s).update_status(appt_id, listing.owner, AppointmentStatusUpdate(status="confirmed"))
    msgs = await _messages(async_client, listing.seeker, conv_id)
    assert PHONE in msgs[0]["content"] and msgs[0]["contact_hidden"] is False
    assert "olu@example.org" in msgs[1]["content"]
    assert msgs[-1]["message_type"] == "system" and msgs[-1]["content"] == VISIT_CONFIRMED_NOTE

    # Cancelling later doesn't hide what both have seen; and the note isn't repeated.
    async with AsyncSessionLocal() as s:
        await AppointmentService(s).update_status(appt_id, listing.seeker, AppointmentStatusUpdate(status="cancelled"))
    msgs = await _messages(async_client, listing.owner, conv_id)
    assert PHONE in msgs[0]["content"]
    assert sum(m["content"] == VISIT_CONFIRMED_NOTE for m in msgs) == 1


async def test_direct_chats_are_not_masked(async_client, listing):
    conv = (await async_client.post(f"{API}/messaging/conversations", headers=auth(listing.seeker), json={
        "participant_user_ids": [str(listing.other)], "type": "direct"})).json()
    await async_client.post(f"{API}/messaging/messages", headers=auth(listing.seeker),
                            json={"conversation_id": conv["conversation_id"], "content": f"Call {PHONE}"})
    [msg] = await _messages(async_client, listing.other, conv["conversation_id"])
    assert PHONE in msg["content"] and msg["contact_hidden"] is False


# ---------------------------------------------------------------- response-time badge

async def _chat(owner, asker, asked_at, reply_after=None, system_note=False):
    async with AsyncSessionLocal() as s:
        conv = Conversation(type="property_inquiry", status="active")
        s.add(conv)
        await s.flush()
        s.add_all([ConversationParticipant(conversation_id=conv.id, user_id=owner),
                   ConversationParticipant(conversation_id=conv.id, user_id=asker)])
        s.add(Message(conversation_id=conv.id, sender_id=asker, content="Is it available?", sent_at=asked_at))
        if system_note:
            s.add(Message(conversation_id=conv.id, sender_id=owner, content=VISIT_CONFIRMED_NOTE,
                          message_type="system", sent_at=asked_at + timedelta(minutes=1)))
        if reply_after is not None:
            s.add(Message(conversation_id=conv.id, sender_id=owner, content="Yes!", sent_at=asked_at + reply_after))
        await s.commit()


async def test_owner_response_badge(async_client, listing):
    now = datetime.now(timezone.utc)
    assert await _badge(listing) is None  # no chats yet

    await _chat(listing.owner, listing.seeker, now - timedelta(days=3), timedelta(minutes=20))
    await _chat(listing.owner, listing.other, now - timedelta(days=2), timedelta(minutes=40))
    assert MIN_CHATS == 3 and await _badge(listing) is None  # too few to judge

    # A system note "from" the owner is not a reply.
    await _chat(listing.owner, listing.seeker, now - timedelta(days=1), None, system_note=True)
    badge = await _badge(listing)
    assert badge["chats"] == 3 and badge["reply_rate"] == pytest.approx(0.67, abs=0.01)
    assert badge["median_reply_minutes"] == 30
    assert badge["label"] == "Usually replies within an hour"

    # It's on the listing page response.
    res = await async_client.get(f"{API}/properties/{listing.property_id}")
    assert res.status_code == 200
    assert res.json()["owner_response"]["label"] == "Usually replies within an hour"


async def _badge(listing):
    async with AsyncSessionLocal() as s:
        return await owner_response(s, listing.owner)
