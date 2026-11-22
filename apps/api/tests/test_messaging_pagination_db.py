"""Chat history paging against a real database: latest page first, chronological order."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.modules.messaging.models import Conversation, ConversationParticipant, Message
from app.modules.messaging.service import MessagingService
from app.modules.users.models import User


@pytest.fixture
async def chat():
    async with AsyncSessionLocal() as session:
        user = User(id=uuid4(), email=f"page-{uuid4().hex[:8]}@example.test", hashed_password="x", full_name="Pager")
        session.add(user)
        conv = Conversation(id=uuid4())
        session.add(conv)
        await session.flush()
        session.add(ConversationParticipant(conversation_id=conv.id, user_id=user.id))
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msgs = []
        for i in range(5):
            m = Message(id=uuid4(), conversation_id=conv.id, sender_id=user.id,
                        content=f"m{i}", sent_at=base + timedelta(minutes=i))
            session.add(m)
            msgs.append(m)
        user_id, conv_id, msg_ids = user.id, conv.id, [m.id for m in msgs]
        await session.commit()

        yield session, user_id, conv_id, msg_ids

        await session.rollback()
        await session.execute(delete(Conversation).where(Conversation.id == conv_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_first_page_is_latest_messages_in_chronological_order(chat):
    session, user_id, conv_id, _ = chat
    page = await MessagingService(session).get_messages(conv_id, user_id, limit=3)
    assert [m.content for m in page] == ["m2", "m3", "m4"]


async def test_paging_back_with_before_id(chat):
    session, user_id, conv_id, ids = chat
    page = await MessagingService(session).get_messages(conv_id, user_id, limit=3, before_id=ids[2])
    assert [m.content for m in page] == ["m0", "m1"]
