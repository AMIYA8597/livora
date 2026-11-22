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
