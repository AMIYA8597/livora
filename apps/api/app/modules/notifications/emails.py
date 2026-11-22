"""
Builds transactional emails for domain events.

Builders run inside the request (they need the DB session) and return plain
`QueuedEmail` values. Routers hand those to FastAPI BackgroundTasks, so delivery
happens after the response and never touches the request's (closed) session.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.infrastructure.email import send_templated_email
from app.modules.users.models import User


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


def enqueue(background_tasks: BackgroundTasks, emails: List[QueuedEmail]) -> None:
    for email in emails:
        background_tasks.add_task(
            send_templated_email, email.to, email.template, email.context, email.idempotency_key
        )


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
