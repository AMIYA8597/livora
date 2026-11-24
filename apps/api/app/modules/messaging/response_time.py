"""
How quickly an owner answers chats: the badge on a listing ("Usually replies within an hour").

Counted over the owner's one-to-one chats that someone else started in the last RESPONSE_DAYS:
the time from the other person's first message to the owner's first reply after it (replies
after REPLY_WINDOW don't count as replies). Nothing is shown until MIN_CHATS chats, so one slow
week, or a brand-new owner, isn't judged on a single chat.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

RESPONSE_DAYS = 90
REPLY_WINDOW_DAYS = 7
MIN_CHATS = 3


def response_label(reply_rate: float, median_minutes: Optional[float]) -> str:
    if reply_rate < 0.5 or median_minutes is None:
        return "Often slow to reply"
    if median_minutes <= 60:
        return "Usually replies within an hour"
    if median_minutes <= 4 * 60:
        return "Usually replies within a few hours"
    if median_minutes <= 24 * 60:
        return "Usually replies within a day"
    return "Usually replies within a few days"


async def owner_response(db: AsyncSession, owner_id: UUID) -> Optional[dict]:
    row = (await db.execute(text(
        """
        WITH firsts AS (
            SELECT m.conversation_id, min(m.sent_at) AS asked_at
            FROM conversation_participants cp
            JOIN conversations c ON c.id = cp.conversation_id AND c.type <> 'group'
            JOIN messages m ON m.conversation_id = cp.conversation_id
                           AND m.sender_id <> cp.user_id AND NOT m.is_deleted
                           AND m.message_type <> 'system'
            WHERE cp.user_id = :owner AND m.sent_at > now() - make_interval(days => :days)
            GROUP BY m.conversation_id
        ), replies AS (
            SELECT f.conversation_id, f.asked_at,
                   (SELECT min(r.sent_at) FROM messages r
                    WHERE r.conversation_id = f.conversation_id AND r.sender_id = :owner
                      AND NOT r.is_deleted AND r.message_type <> 'system'
                      AND r.sent_at > f.asked_at
                      AND r.sent_at <= f.asked_at + make_interval(days => :window)) AS replied_at
            FROM firsts f
        )
        SELECT count(*) AS chats,
               count(replied_at) AS answered,
               percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY extract(epoch FROM replied_at - asked_at) / 60.0
               ) FILTER (WHERE replied_at IS NOT NULL) AS median_minutes
        FROM replies
        """
    ), {"owner": owner_id, "days": RESPONSE_DAYS, "window": REPLY_WINDOW_DAYS})).one()
    chats, answered, median = int(row.chats), int(row.answered), row.median_minutes
    if chats < MIN_CHATS:
        return None
    rate = answered / chats
    median_minutes = None if median is None else round(float(median))
    return {
        "label": response_label(rate, median_minutes),
        "reply_rate": round(rate, 2),
        "median_reply_minutes": median_minutes,
        "chats": chats,
    }
