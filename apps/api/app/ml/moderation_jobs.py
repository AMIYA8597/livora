"""
Outbox handlers that apply moderation decisions (see moderation.py) to messages and listings.

Idempotent: re-running recomputes the same decision, metadata is overwritten rather than
appended, and the automatic report is protected by a partial unique index (migration 009).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.ml.llm import LLMUnavailable, llm_configured
from app.ml.moderation import Decision, Verdict, classify_with_llm, decide, prescreen
from app.modules.messaging.models import ConversationParticipant, Message, OutboxEvent
from app.modules.properties.models import Property

logger = logging.getLogger("flatmate.ml.moderation")

MESSAGE_MODERATE_EVENT = "message.moderate"
PROPERTY_MODERATE_EVENT = "property.moderate"
CONTEXT_MESSAGES = 6


def ai_moderation_on() -> bool:
    return settings.AI_MODERATION_ENABLED and llm_configured()


def queue_message_moderation(db: AsyncSession, message_id: UUID) -> None:
    db.add(OutboxEvent(event_type=MESSAGE_MODERATE_EVENT, payload={"message_id": str(message_id)}, status="pending"))


def queue_property_moderation(db: AsyncSession, property_id: UUID) -> None:
    db.add(OutboxEvent(event_type=PROPERTY_MODERATE_EVENT, payload={"property_id": str(property_id)}, status="pending"))


async def _auto_report(db: AsyncSession, target_type: str, target_id: UUID, decision: Decision) -> None:
    await db.execute(text("""
        INSERT INTO moderation_reports (id, reporter_id, target_type, target_id, reason, description,
                                        status, created_at, source, details)
        VALUES (gen_random_uuid(), NULL, :target_type, :target_id, :reason, :description,
                'open', now(), 'auto', CAST(:details AS jsonb))
        ON CONFLICT (target_type, target_id) WHERE source = 'auto' DO NOTHING
    """), {
        "target_type": target_type, "target_id": target_id,
        "reason": f"auto_{decision.label}"[:100],
        "description": str(decision.details.get("reason") or "Flagged by automatic safety checks"),
        "details": json.dumps(decision.details, default=str),
    })


async def _verdict(content: str, kind: str, context: List[str], signals: List[str]) -> Optional[Verdict]:
    if not ai_moderation_on():
        return None
    try:
        return await classify_with_llm(content, kind=kind, context=context, signals=signals)  # type: ignore[arg-type]
    except LLMUnavailable as exc:
        logger.warning("AI moderation unavailable, using rules: %s", exc)
        return None


async def publish_realtime(event: str, data: Dict[str, Any], user_ids: List[UUID]) -> None:
    """Best effort: works in the API process (broker) and in workers when Redis is configured."""
    try:
        from app.modules.messaging.broker import CHANNEL_CHAT_EVENTS, broker

        if broker.redis is not None or broker._local_listeners:  # noqa: SLF001 - same package family
            await broker.publish(event, data, target_user_ids=user_ids)
            return
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await client.publish(CHANNEL_CHAT_EVENTS, json.dumps({
                "version": "1.0", "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(), "correlation_id": None,
                "target_user_ids": [str(u) for u in user_ids], "data": data,
            }))
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001 - clients also see the warning on their next fetch
        logger.info("Realtime moderation update not delivered: %s", type(exc).__name__)


async def moderate_message(session_factory: async_sessionmaker[AsyncSession], message_id: UUID) -> Dict[str, Any]:
    async with session_factory() as db:
        msg = (await db.execute(select(Message).where(Message.id == message_id))).scalar_one_or_none()
        if msg is None or msg.is_deleted or not msg.content:
            return {"message_id": str(message_id), "skipped": True}

        earlier = (await db.execute(
            select(Message.sender_id, Message.content)
            .where(Message.conversation_id == msg.conversation_id, Message.sent_at < msg.sent_at,
                   Message.is_deleted.is_(False))
            .order_by(Message.sent_at.desc()).limit(CONTEXT_MESSAGES)
        )).all()
        # Role labels only: no names or ids go to the model.
        context = [
            f"{'author' if sender == msg.sender_id else 'other person'}: {(content or '')[:500]}"
            for sender, content in reversed(earlier)
        ]
        pre = prescreen(msg.content)
        decision = decide(pre, await _verdict(msg.content, "message", context, pre.signals))

        metadata = dict(msg.metadata_ or {})
        before = metadata.get("safety_warning")
        if decision.warning:
            metadata["safety_warning"] = decision.warning
        else:
            metadata.pop("safety_warning", None)
        metadata["moderation"] = {"label": decision.label, "source": decision.source}
        msg.metadata_ = metadata
        if decision.report:
            await _auto_report(db, "message", msg.id, decision)
        recipients = list((await db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == msg.conversation_id,
                ConversationParticipant.is_active.is_(True),
            )
        )).scalars().all())
        await db.commit()

    if metadata.get("safety_warning") != before:
        await publish_realtime("message.moderated", {
            "id": str(msg.id), "conversation_id": str(msg.conversation_id),
            "safety_warning": metadata.get("safety_warning"),
        }, recipients)
    return {"message_id": str(message_id), "label": decision.label, "source": decision.source,
            "reported": decision.report}


def listing_text(prop: Property) -> str:
    return (
        f"Title: {prop.title}\nType: {prop.configuration} {prop.property_category}\n"
        f"Locality: {prop.address_display}, {prop.city}\n"
        f"Monthly rent: INR {prop.monthly_rent}; deposit: INR {prop.security_deposit}\n"
        f"Description: {prop.description}"
    )


async def moderate_property(session_factory: async_sessionmaker[AsyncSession], property_id: UUID) -> Dict[str, Any]:
    async with session_factory() as db:
        prop = (await db.execute(select(Property).where(Property.id == property_id))).scalar_one_or_none()
        if prop is None:
            return {"property_id": str(property_id), "skipped": True}
        pre = prescreen(f"{prop.title}\n{prop.description}")
        decision = decide(pre, await _verdict(listing_text(prop), "listing", [], pre.signals))
        # Listings are never unpublished automatically; a moderator decides.
        if decision.report:
            await _auto_report(db, "property", prop.id, decision)
            await db.commit()
    return {"property_id": str(property_id), "label": decision.label, "reported": decision.report}
