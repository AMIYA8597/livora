"""
Contact details in listing chats stay inside the chat until a visit is confirmed.

In an "Ask the owner" chat (type `property_inquiry`), phone numbers and email addresses are
hidden from both people until the owner confirms a visit to that listing with this seeker.
Moving to WhatsApp or a phone call before anyone has seen the place is where most rental scams
start (pay a "token" to hold it, keys by courier...), and it also keeps a seeker's number away
from owners and brokers who only want to collect leads.

Hiding happens when messages are READ, never when stored: once the visit is confirmed, earlier
messages show their numbers too. Confirming also stamps the chat (`contacts_shared_at` in its
context metadata, see `share_contacts_after_visit`), so a visit cancelled later doesn't hide
numbers both people have already seen. Every path that returns message text goes through here:
history, send responses, realtime events, edits, the inbox preview and search, and smart-reply
context. Moderation (app/ml/moderation*) still sees the full text.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

LISTING_CHAT = "property_inquiry"
UNLOCKING_VISITS = ("confirmed", "completed")
HIDDEN = "[contact hidden until a visit is confirmed]"

# Indian mobiles (6-9 then 9 digits), with +91/91/0 and any spaces, dots, dashes or brackets
# between digits: "98765 43210", "+91-98765-43210", "(0)98 7654 3210".
_PHONE = re.compile(r"(?<![\w+])(?:(?:\+\s*91|\b91|\b0)[\s.\-()]*|\()?[6-9](?:[\s.\-()]*\d){9}(?!\d)")
# Ordinary email addresses. UPI ids ("name@okaxis") have no dot after the @ and are left alone;
# the scam pre-screen warns about those separately.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


def hide_contacts(content: Optional[str]) -> Tuple[Optional[str], bool]:
    """(text with phone numbers and emails replaced, whether anything was replaced)."""
    if not content:
        return content, False
    hidden = _EMAIL.sub(HIDDEN, content)
    hidden = _PHONE.sub(HIDDEN, hidden)
    return hidden, hidden != content


async def locked_conversations(db: AsyncSession, conversation_ids: Iterable[UUID]) -> Set[UUID]:
    """Which of these conversations are listing chats without a confirmed visit between their
    owner and seeker for that listing. A chat whose listing was deleted stays locked."""
    ids = list({cid for cid in conversation_ids if cid is not None})
    if not ids:
        return set()
    rows = await db.execute(text(
        """
        SELECT c.id FROM conversations c
        WHERE c.id = ANY(:ids) AND c.type = :listing_chat
          AND NOT (c.context_metadata ? 'contacts_shared_at')
          AND NOT EXISTS (
              SELECT 1 FROM appointments a
              WHERE a.property_id = c.property_id
                AND a.status = ANY(:unlocking)
                AND EXISTS (SELECT 1 FROM conversation_participants p
                            WHERE p.conversation_id = c.id AND p.user_id = a.host_id)
                AND EXISTS (SELECT 1 FROM conversation_participants p
                            WHERE p.conversation_id = c.id AND p.user_id = a.applicant_id)
          )
        """
    ), {"ids": ids, "listing_chat": LISTING_CHAT, "unlocking": list(UNLOCKING_VISITS)})
    return {row[0] for row in rows.all()}


async def is_locked(db: AsyncSession, conversation_id: UUID) -> bool:
    return conversation_id in await locked_conversations(db, [conversation_id])


VISIT_CONFIRMED_NOTE = "Visit confirmed. Phone numbers and emails in this chat are now visible to both of you."


async def share_contacts_after_visit(db: AsyncSession, property_id: UUID, host_id: UUID, applicant_id: UUID) -> None:
    """The owner confirmed a visit: unlock their listing chat with this seeker (if they have one)
    and say so in it. Commits; the realtime event is best effort."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from app.modules.messaging.models import Conversation, ConversationParticipant, Message
    from app.modules.messaging.service import jsonable, message_dict
    from app.modules.messaging.websocket import manager

    conv = (await db.execute(
        select(Conversation)
        .join(ConversationParticipant)
        .where(
            Conversation.type == LISTING_CHAT,
            Conversation.property_id == property_id,
            ConversationParticipant.user_id.in_([host_id, applicant_id]),
        )
        .group_by(Conversation.id)
        .having(func.count(ConversationParticipant.user_id) == 2)
    )).scalars().first()
    if conv is None or "contacts_shared_at" in (conv.context_metadata or {}):
        return
    now = datetime.now(timezone.utc)
    conv.context_metadata = {**(conv.context_metadata or {}), "contacts_shared_at": now.isoformat()}
    note = Message(conversation_id=conv.id, sender_id=host_id, content=VISIT_CONFIRMED_NOTE,
                   message_type="system", sent_at=now)
    db.add(note)
    conv.last_message_at = now
    await db.commit()
    await db.refresh(note)
    try:
        await manager.broadcast_to_users(
            event_type="message.created",
            data=jsonable({**message_dict(note, []), "status": "sent"}),
            user_ids=[host_id, applicant_id],
        )
    except Exception:  # noqa: BLE001 - the note is saved; clients see it on next load
        pass
