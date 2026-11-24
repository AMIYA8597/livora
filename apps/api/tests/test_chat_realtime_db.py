"""
Live chat against a real database: socket authentication, read receipts, inbox queries,
presence privacy and the "unread message" email.

The WebSocket tests drive the real ASGI app in-process (httpx's ASGI transport has no
WebSocket support), so they run on the same event loop as the database.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.modules.messaging.models import (
    Conversation, ConversationParticipant, ConversationPreference, ConversationReadCursor, Message, OutboxEvent,
)
from app.modules.messaging.router import authenticate_socket_token
from app.modules.messaging.schemas import SendMessageRequest
from app.modules.messaging.service import MessagingService
from app.modules.notifications.emails import queue_unread_message_emails
from app.modules.notifications.models import Notification
from app.modules.users.models import User

WS_PATH = f"{settings.API_V1_PREFIX}/messaging/ws"


# --------------------------------------------------------------------------- fixtures

@pytest.fixture
async def people():
    """Three users; A and B share a conversation with two messages from B, C is a stranger."""
    async with AsyncSessionLocal() as s:
        users = [
            User(id=uuid4(), email=f"rt-{uuid4().hex[:8]}@example.com", hashed_password="x", full_name=name)
            for name in ("Asha", "Bilal", "Chen")
        ]
        s.add_all(users)
        conv = Conversation(id=uuid4(), type="direct", status="active",
                            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        s.add(conv)
        await s.flush()
        a, b, c = users
        s.add_all([
            ConversationParticipant(conversation_id=conv.id, user_id=a.id),
            ConversationParticipant(conversation_id=conv.id, user_id=b.id),
        ])
        base = datetime(2026, 1, 2, tzinfo=timezone.utc)
        msgs = [
            Message(id=uuid4(), conversation_id=conv.id, sender_id=b.id, content=f"hello {i}",
                    sent_at=base + timedelta(minutes=i))
            for i in range(2)
        ]
        s.add_all(msgs)
        await s.commit()
        ids = {"a": a.id, "b": b.id, "c": c.id, "conv": conv.id, "m0": msgs[0].id, "m1": msgs[1].id}

    yield ids

    async with AsyncSessionLocal() as s:
        await s.execute(delete(OutboxEvent).where(
            OutboxEvent.payload["conversation_id"].astext == str(ids["conv"])))
        await s.execute(delete(OutboxEvent).where(
            OutboxEvent.payload["throttle_key"].astext.like(f"%{ids['conv']}%")))
        await s.execute(delete(Notification).where(Notification.reference_id == ids["conv"]))
        await s.execute(delete(Conversation).where(Conversation.id == ids["conv"]))
        await s.execute(delete(User).where(User.id.in_([ids["a"], ids["b"], ids["c"]])))
        await s.commit()


def _token(user_id) -> str:
    return create_access_token(subject=str(user_id), roles=["seeker"])


class AsgiSocket:
    """Minimal in-process WebSocket client for the ASGI app."""

    def __init__(self, path: str = WS_PATH):
        self.scope = {
            "type": "websocket", "asgi": {"version": "3.0"}, "scheme": "ws", "path": path,
            "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": [(b"host", b"testserver"), (b"origin", b"http://localhost:3000")],
            "client": ("127.0.0.1", 50000), "server": ("testserver", 80), "subprotocols": [],
        }
        self.inbox: asyncio.Queue = asyncio.Queue()
        self.outbox: asyncio.Queue = asyncio.Queue()
        self.task = None

    async def __aenter__(self):
        await self.inbox.put({"type": "websocket.connect"})
        self.task = asyncio.create_task(app(self.scope, self.inbox.get, self.outbox.put))
        return self

    async def __aexit__(self, *exc):
        await self.inbox.put({"type": "websocket.disconnect", "code": 1000})
        try:
            await asyncio.wait_for(self.task, timeout=5)
        except (asyncio.TimeoutError, Exception):
            self.task.cancel()

    async def send(self, event: str, data: dict) -> None:
        await self.inbox.put({"type": "websocket.receive", "text": json.dumps({"event": event, "data": data})})

    async def next(self, timeout: float = 5.0) -> dict:
        """Next ASGI message, skipping the accept."""
        while True:
            msg = await asyncio.wait_for(self.outbox.get(), timeout=timeout)
            if msg["type"] != "websocket.accept":
                return msg

    async def next_event(self, name: str, timeout: float = 5.0) -> dict:
        while True:
            msg = await self.next(timeout)
            assert msg["type"] == "websocket.send", msg
            envelope = json.loads(msg["text"])
            if envelope["event"] == name:
                return envelope


# --------------------------------------------------------------------------- socket auth

async def test_socket_token_must_be_an_access_token_for_an_active_user(people):
    assert (await authenticate_socket_token(_token(people["a"])))[0] == people["a"]
    assert await authenticate_socket_token(create_refresh_token(str(people["a"]), ["seeker"])) is None
    assert await authenticate_socket_token("not-a-jwt") is None
    assert await authenticate_socket_token(None) is None

    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.id == people["a"]))).scalar_one()
        user.is_active = False
        await s.commit()
    assert await authenticate_socket_token(_token(people["a"])) is None


async def test_socket_closes_without_auth_frame(people):
    async with AsgiSocket() as ws:
        await ws.send("ping", {})
        closed = await ws.next()
        assert closed["type"] == "websocket.close" and closed["code"] == 4003


async def test_socket_auth_frame_then_typing_reaches_only_members(people):
    async with AsgiSocket() as a, AsgiSocket() as b, AsgiSocket() as c:
        for sock, who in ((a, "a"), (b, "b"), (c, "c")):
            await sock.send("auth", {"token": _token(people[who])})
            ready = await sock.next_event("connection.ready")
            assert ready["data"]["user_id"] == str(people[who])

        await a.send("typing.started", {"conversation_id": str(people["conv"])})
        typing = await b.next_event("typing.started")
        assert typing["data"] == {"conversation_id": str(people["conv"]), "user_id": str(people["a"])}

        # A stranger can't send typing indicators into someone else's conversation.
        await c.send("typing.started", {"conversation_id": str(people["conv"])})
        await a.send("ping", {})
        await a.next_event("pong")
        with pytest.raises(asyncio.TimeoutError):
            await a.next_event("typing.started", timeout=0.5)


async def test_message_sent_over_socket_is_delivered_with_attachments_field(people):
    async with AsgiSocket() as a, AsgiSocket() as b:
        await a.send("auth", {"token": _token(people["a"])})
        await b.send("auth", {"token": _token(people["b"])})
        await a.next_event("connection.ready")
        await b.next_event("connection.ready")

        await a.send("message.send", {"conversation_id": str(people["conv"]), "content": "hi Bilal",
                                      "idempotency_key": "rt-1"})
        created = await b.next_event("message.created")
        assert created["data"]["content"] == "hi Bilal"
        assert created["data"]["attachments"] == []
        assert "target_user_ids" not in created  # routing details stay server-side


# --------------------------------------------------------------------------- read receipts

async def test_mark_read_rules(people):
    async with AsyncSessionLocal() as s:
        service = MessagingService(s)
        with pytest.raises(ForbiddenException):
            await service.mark_read(people["conv"], people["c"], people["m1"])  # stranger

        await service.mark_read(people["conv"], people["a"], people["m1"])
        # Loading an older page must not move the cursor back.
        await service.mark_read(people["conv"], people["a"], people["m0"])
        cursor = (await s.execute(select(ConversationReadCursor).where(
            ConversationReadCursor.conversation_id == people["conv"],
            ConversationReadCursor.user_id == people["a"],
        ))).scalar_one()
        assert cursor.last_read_message_id == people["m1"]

        with pytest.raises(NotFoundException):
            await service.mark_read(people["conv"], people["a"], uuid4())

        details = await service.get_conversation(people["conv"], people["b"])
        assert [rc["user_id"] for rc in details["read_cursors"]] == [people["a"]]


async def test_inbox_last_message_and_unread_count(people):
    async with AsyncSessionLocal() as s:
        convs = await MessagingService(s).list_conversations(people["a"])
        mine = next(c for c in convs if c["id"] == people["conv"])
        assert mine["last_message"]["content"] == "hello 1"
        assert mine["unread_count"] == 2

        # A deleted latest message: the inbox shows the latest one that isn't deleted.
        m1 = (await s.execute(select(Message).where(Message.id == people["m1"]))).scalar_one()
        m1.is_deleted = True
        await s.commit()
        convs = await MessagingService(s).list_conversations(people["a"], search_query="bilal")
        mine = next(c for c in convs if c["id"] == people["conv"])
        assert mine["last_message"]["content"] == "hello 0"
        assert mine["unread_count"] == 1


# --------------------------------------------------------------------------- notifications

async def test_send_respects_mute_and_schedules_unread_email(people):
    async with AsyncSessionLocal() as s:
        s.add(ConversationPreference(conversation_id=people["conv"], user_id=people["b"], is_muted=True))
        await s.commit()
        msg = await MessagingService(s).send_message(
            people["a"], SendMessageRequest(conversation_id=people["conv"], content="are you there?"))

        notifs = (await s.execute(select(Notification).where(Notification.reference_id == people["conv"]))).scalars().all()
        assert notifs == []  # B muted the conversation

        event = (await s.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == "message.created",
            OutboxEvent.payload["id"].astext == str(msg.id),
        ))).scalar_one()
        assert event.payload["recipient_ids"] == [str(people["b"])]
        assert "content" not in event.payload  # no message text at rest in the outbox
        assert event.next_attempt_at > datetime.now(timezone.utc) + timedelta(minutes=5)


async def test_unread_email_is_sent_once_and_only_if_still_unread(people):
    payload = {"id": str(people["m1"]), "conversation_id": str(people["conv"]),
               "sender_id": str(people["b"]), "recipient_ids": [str(people["a"])]}
    async with AsyncSessionLocal() as s:
        assert await queue_unread_message_emails(s, payload) == 1
        assert await queue_unread_message_emails(s, payload) == 0  # throttled
        email = (await s.execute(select(OutboxEvent).where(
            OutboxEvent.payload["throttle_key"].astext == f"new_message:{people['a']}:{people['conv']}"
        ))).scalar_one()
        assert email.payload["template"] == "new_message"
        assert "hello" not in json.dumps(email.payload)  # message text is never emailed
        assert email.payload["context"]["sender_name"] == "Bilal"

        # Once read, nobody is emailed (simulate a fresh throttle window by removing the row).
        await s.delete(email)
        await s.commit()
        await MessagingService(s).mark_read(people["conv"], people["a"], people["m1"])
        assert await queue_unread_message_emails(s, payload) == 0


# --------------------------------------------------------------------------- presence

async def test_presence_is_private_to_conversation_contacts(people, async_client):
    def auth(who):
        return {"Authorization": f"Bearer {_token(people[who])}"}

    ok = await async_client.get(f"{settings.API_V1_PREFIX}/messaging/presence/{people['b']}", headers=auth("a"))
    assert ok.status_code == 200 and ok.json()["status"] in ("online", "offline")
    hidden = await async_client.get(f"{settings.API_V1_PREFIX}/messaging/presence/{people['b']}", headers=auth("c"))
    assert hidden.status_code == 404


def test_send_request_validation():
    from pydantic import ValidationError

    conv = uuid4()
    with pytest.raises(ValidationError):
        SendMessageRequest(conversation_id=conv, content="   ")  # empty, no attachment
    with pytest.raises(ValidationError):
        SendMessageRequest(conversation_id=conv, content="x" * 4001)
    with pytest.raises(ValidationError):
        SendMessageRequest(conversation_id=conv, content="hi", message_type="system")
    with pytest.raises(ValidationError):
        SendMessageRequest(conversation_id=conv, content="hi", idempotency_key="k" * 65)
    ok = SendMessageRequest(conversation_id=conv, content="  hi  ", metadata={"safety_warning": "forged"})
    assert ok.content == "hi" and ok.metadata == {}
    assert SendMessageRequest(conversation_id=conv, content="", attachment_ids=[uuid4()]).content == ""


# --------------------------------------------------------------------------- disabled accounts

async def _connect(sock: "AsgiSocket", user_id) -> None:
    await sock.send("auth", {"token": _token(user_id)})
    await sock.next_event("connection.ready")


async def _next_close(sock: "AsgiSocket", timeout: float = 5.0) -> dict:
    while True:
        msg = await sock.next(timeout)
        if msg["type"] == "websocket.close":
            return msg


async def test_staff_deactivation_closes_the_accounts_sockets_at_once(people):
    from app.modules.administration.service import AdminService

    async with AsgiSocket() as a1, AsgiSocket() as a2, AsgiSocket() as b:
        for sock, who in ((a1, "a"), (a2, "a"), (b, "b")):
            await _connect(sock, people[who])

        async with AsyncSessionLocal() as s:
            await AdminService(s).update_user_status(people["a"], False)

        for sock in (a1, a2):  # every tab, not just one
            closed = await _next_close(sock)
            assert closed["code"] == 4003
        # Other people stay connected, and the internal event never reaches a client.
        await b.send("ping", {})
        pong = await b.next_event("pong")
        assert pong["event"] == "pong"


async def test_requesting_deletion_closes_the_accounts_sockets(people):
    from app.core.security import get_password_hash
    from app.modules.users.privacy import request_deletion

    async with AsyncSessionLocal() as s:
        user = (await s.execute(select(User).where(User.id == people["a"]))).scalar_one()
        user.hashed_password = get_password_hash("Correct-horse-1")
        await s.commit()

    async with AsgiSocket() as a:
        await _connect(a, people["a"])
        async with AsyncSessionLocal() as s:
            user = (await s.execute(select(User).where(User.id == people["a"]))).scalar_one()
            await request_deletion(s, user, "Correct-horse-1")
        closed = await _next_close(a)
        assert closed["code"] == 4003


async def test_heartbeat_recheck_closes_a_socket_whose_close_event_was_missed(people, monkeypatch):
    from app.modules.messaging import websocket as ws_mod

    async with AsgiSocket() as a:
        await _connect(a, people["a"])
        # Disabled without the broker event (e.g. the pub/sub message was lost).
        async with AsyncSessionLocal() as s:
            user = (await s.execute(select(User).where(User.id == people["a"]))).scalar_one()
            user.is_active = False
            await s.commit()

        await a.send("ping", {})
        assert (await a.next_event("pong"))["event"] == "pong"  # not due yet: no query per ping

        monkeypatch.setattr(ws_mod, "ACCOUNT_RECHECK_SECONDS", 0)
        await a.send("ping", {})
        closed = await _next_close(a)
        assert closed["code"] == 4003
