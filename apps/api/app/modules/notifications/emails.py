"""
Builds transactional emails for domain events and queues them durably.

Builders run inside the request and return plain `QueuedEmail` values. `enqueue`
writes them to the transactional outbox (committed before the response), then kicks
a dispatch after the response for low latency. The Celery beat sweep retries anything
that fails, or that was left behind because the process died, so mail is never lost
to a restart or a provider outage.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.modules.messaging.models import OutboxEvent
from app.modules.users.models import User
from app.workers.outbox import EMAIL_EVENT, dispatch_pending

logger = logging.getLogger("flatmate.notifications")


@dataclass(frozen=True)
class QueuedEmail:
    to: str
    template: str
    context: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None


def web_url(path: str) -> str:
    return f"{settings.WEB_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def idempotency_key(*parts: object) -> str:
    """Stable per-event key so provider-side retries never send duplicates."""
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:48]


async def enqueue(db: AsyncSession, background_tasks: BackgroundTasks, emails: List[QueuedEmail]) -> None:
    if not emails:
        return
    for email in emails:
        db.add(OutboxEvent(
            event_type=EMAIL_EVENT,
            payload={
                "to": email.to,
                "template": email.template,
                "context": {k: (v if isinstance(v, (int, float, bool)) or v is None else str(v))
                            for k, v in email.context.items()},
                "idempotency_key": email.idempotency_key,
            },
            status="pending",
        ))
    await db.commit()
    background_tasks.add_task(dispatch_now)


async def dispatch_now() -> None:
    """Best-effort immediate dispatch after the response. Failures stay queued for the sweep."""
    try:
        await dispatch_pending(AsyncSessionLocal)
    except Exception as exc:  # noqa: BLE001 - the beat sweep is the safety net
        logger.warning("Immediate outbox dispatch failed: %s", type(exc).__name__)


async def queue_unread_message_emails(db: AsyncSession, payload: Dict[str, Any]) -> int:
    """For a `message.created` outbox event: email each recipient who still hasn't read it.

    Skips recipients who have read the conversation since, muted it, left it or been
    deactivated, and anyone already emailed about this conversation within
    CHAT_EMAIL_THROTTLE_MINUTES. Returns how many emails were queued.
    """
    from datetime import datetime, timedelta, timezone

    from app.modules.messaging.models import (
        Conversation, ConversationParticipant, ConversationPreference, ConversationReadCursor, Message,
    )
    from app.modules.messaging.service import is_muted

    try:
        message_id = UUID(str(payload["id"]))
        conversation_id = UUID(str(payload["conversation_id"]))
        recipient_ids = [UUID(str(r)) for r in payload.get("recipient_ids") or []]
    except (KeyError, ValueError):
        return 0
    if not recipient_ids:
        return 0

    message = (await db.execute(select(Message).where(Message.id == message_id))).scalar_one_or_none()
    conversation = (await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )).scalar_one_or_none()
    if message is None or message.is_deleted or conversation is None or conversation.status != "active":
        return 0

    active = set((await db.execute(
        select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id.in_(recipient_ids),
            ConversationParticipant.is_active.is_(True),
        )
    )).scalars().all())
    read_at: Dict[Any, Any] = {user: last_read for user, last_read in (await db.execute(
        select(ConversationReadCursor.user_id, ConversationReadCursor.last_read_at).where(
            ConversationReadCursor.conversation_id == conversation_id,
            ConversationReadCursor.user_id.in_(recipient_ids),
        )
    )).all()}
    prefs = {p.user_id: p for p in (await db.execute(
        select(ConversationPreference).where(
            ConversationPreference.conversation_id == conversation_id,
            ConversationPreference.user_id.in_(recipient_ids),
        )
    )).scalars().all()}
    users = await _users(db, message.sender_id, *recipient_ids)
    sender = users.get(message.sender_id)

    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=settings.CHAT_EMAIL_THROTTLE_MINUTES)
    queued = 0
    for rid in recipient_ids:
        user = users.get(rid)
        if rid not in active or user is None or not user.is_active or not user.email:
            continue
        last_read = read_at.get(rid)
        if last_read is not None and last_read >= message.sent_at:
            continue  # they've seen it
        if is_muted(prefs.get(rid), now):
            continue
        throttle_key = f"new_message:{rid}:{conversation_id}"
        recent = (await db.execute(
            select(OutboxEvent.id).where(
                OutboxEvent.event_type == EMAIL_EVENT,
                OutboxEvent.payload["throttle_key"].astext == throttle_key,
                OutboxEvent.created_at >= since,
            ).limit(1)
        )).scalar_one_or_none()
        if recent is not None:
            continue
        db.add(OutboxEvent(
            event_type=EMAIL_EVENT,
            payload={
                "to": user.email,
                "template": "new_message",
                "context": {
                    "name": user.full_name,
                    "sender_name": sender.full_name if sender else "Someone",
                    "conversation_url": web_url(f"/messages?conversationId={conversation_id}"),
                },
                "idempotency_key": idempotency_key("new_message", rid, message_id),
                "throttle_key": throttle_key,
            },
            status="pending",
            created_at=now,
        ))
        queued += 1
    if queued:
        await db.commit()
    return queued


async def _users(db: AsyncSession, *ids: UUID) -> Dict[UUID, User]:
    rows = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().all()
    return {u.id: u for u in rows}


async def application_received(db: AsyncSession, application: Any, property_: Any) -> List[QueuedEmail]:
    users = await _users(db, property_.owner_id, application.applicant_id)
    owner, applicant = users.get(property_.owner_id), users.get(application.applicant_id)
    if not owner or not applicant or not owner.is_active:
        return []
    return [QueuedEmail(
        to=owner.email,
        template="application_received",
        context={
            "name": owner.full_name,
            "applicant_name": applicant.full_name,
            "property_title": property_.title,
            "proposed_rent": application.proposed_rent if application.proposed_rent is not None else "the listed rent",
            "move_in_target": application.move_in_target or "a flexible date",
            "dashboard_url": web_url("/owner/dashboard"),
        },
        idempotency_key=idempotency_key("application_received", application.id),
    )]


async def application_status_changed(
    db: AsyncSession, application: Any, property_: Any, actor_id: UUID
) -> List[QueuedEmail]:
    # Applicants withdrawing their own application don't need to be told about it.
    if actor_id == application.applicant_id:
        return []
    applicant = (await _users(db, application.applicant_id)).get(application.applicant_id)
    if not applicant or not applicant.is_active:
        return []
    return [QueuedEmail(
        to=applicant.email,
        template="application_status",
        context={
            "name": applicant.full_name,
            "property_title": property_.title,
            "status": application.status,
            "dashboard_url": web_url("/dashboard"),
        },
        idempotency_key=idempotency_key("application_status", application.id, application.status),
    )]


async def appointment_requested(db: AsyncSession, appointment: Any, property_: Any) -> List[QueuedEmail]:
    users = await _users(db, appointment.host_id, appointment.applicant_id)
    host, applicant = users.get(appointment.host_id), users.get(appointment.applicant_id)
    if not host or not applicant or not host.is_active:
        return []
    return [QueuedEmail(
        to=host.email,
        template="appointment_requested",
        context={
            "name": host.full_name,
            "applicant_name": applicant.full_name,
            "property_title": property_.title,
            "scheduled_for": appointment.scheduled_at.strftime("%d %b %Y, %H:%M UTC"),
            "dashboard_url": web_url("/appointments"),
        },
        idempotency_key=idempotency_key("appointment_requested", appointment.id),
    )]
