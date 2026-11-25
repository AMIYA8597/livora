"""
Domain events that become in-app notifications (and pushes).

Each function runs after the caller's own commit and never raises: a notification must not
fail the action that caused it. Texts are short and carry no private content: they show on
lock screens. "Someone likes you" deliberately names nobody (seeing who is a Seeker Pro perk).
"""
from __future__ import annotations

import logging
from datetime import timedelta, timezone
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.service import NotificationService
from app.modules.users.models import User

logger = logging.getLogger("flatmate.notifications")
IST = timezone(timedelta(hours=5, minutes=30))

APPLICATION_STATUS_TEXT = {
    "under_review": "is being reviewed",
    "reviewing": "is being reviewed",
    "accepted": "was accepted",
    "approved": "was accepted",
    "rejected": "wasn't successful",
    "withdrawn": "was withdrawn",
}
APPOINTMENT_STATUS_TEXT = {
    "confirmed": "is confirmed",
    "cancelled": "was cancelled",
    "completed": "is marked as done",
    "rescheduled": "needs a new time",
}


async def first_name(db: AsyncSession, user_id: UUID) -> str:
    user = await db.get(User, user_id)
    name = (user.full_name or "").strip() if user else ""
    return name.split()[0] if name else "Someone"


F = TypeVar("F", bound=Callable[..., Awaitable[None]])


def fail_safe(fn: F) -> F:
    """A notification must never fail (or roll back) the action that caused it."""

    @wraps(fn)
    async def wrapper(db: AsyncSession, *args: Any, **kwargs: Any) -> None:
        try:
            await fn(db, *args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.warning("Notification event %s failed", fn.__name__, exc_info=True)
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    return wrapper  # type: ignore[return-value]


async def _notify(db: AsyncSession, **kwargs: Any) -> None:
    try:
        await NotificationService(db).create_notification(**kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("Notification %s failed", kwargs.get("notification_type"), exc_info=True)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass


@fail_safe
async def match_created(db: AsyncSession, user_a: UUID, user_b: UUID, match_id: Optional[UUID]) -> None:
    for me, other in ((user_a, user_b), (user_b, user_a)):
        name = await first_name(db, other)
        await _notify(db, user_id=me, title=f"It's a match with {name}!",
                      body="You both liked each other. Say hello.", notification_type="match_created",
                      reference_id=match_id, link="/matches", idempotency_window_minutes=60 * 24)


@fail_safe
async def like_received(db: AsyncSession, target_id: UUID, super_like: bool) -> None:
    await _notify(db, user_id=target_id,
                  title="Someone super-liked you" if super_like else "Someone new likes you",
                  body="Like them back from your matches to connect.", notification_type="new_interest",
                  link="/matches", idempotency_window_minutes=30)


@fail_safe
async def application_received(db: AsyncSession, application: Any, prop: Any) -> None:
    name = await first_name(db, application.applicant_id)
    await _notify(db, user_id=prop.owner_id, title=f"New application from {name}",
                  body=f"For {prop.title}", notification_type="application_received",
                  reference_id=application.id, link="/owner?tab=applications")


@fail_safe
async def application_status_changed(db: AsyncSession, application: Any, prop: Any, actor_id: UUID,
                                     by_staff: bool = False) -> None:
    text = APPLICATION_STATUS_TEXT.get(application.status)
    if not text:
        return
    if by_staff:  # Flatmate support stepped in: both sides should know it wasn't the other one
        await _notify(db, user_id=application.applicant_id, title=f"Your application {text}",
                      body=f"For {prop.title}. Updated by Flatmate support.",
                      notification_type="application_status_change", reference_id=application.id,
                      link="/dashboard?tab=applications", idempotency_window_minutes=1)
        name = await first_name(db, application.applicant_id)
        await _notify(db, user_id=prop.owner_id, title=f"{name}'s application {text}",
                      body=f"For {prop.title}. Updated by Flatmate support.",
                      notification_type="application_status_change", reference_id=application.id,
                      link="/owner?tab=applications", idempotency_window_minutes=1)
    elif actor_id == application.applicant_id:  # the applicant withdrew: tell the owner
        name = await first_name(db, application.applicant_id)
        await _notify(db, user_id=prop.owner_id, title=f"{name} withdrew their application",
                      body=f"For {prop.title}", notification_type="application_status_change",
                      reference_id=application.id, link="/owner?tab=applications", idempotency_window_minutes=1)
    else:
        await _notify(db, user_id=application.applicant_id, title=f"Your application {text}",
                      body=f"For {prop.title}", notification_type="application_status_change",
                      reference_id=application.id, link="/dashboard?tab=applications", idempotency_window_minutes=1)


@fail_safe
async def appointment_requested(db: AsyncSession, appointment: Any, prop: Any) -> None:
    name = await first_name(db, appointment.applicant_id)
    when = (appointment.scheduled_at.astimezone(IST).strftime("%d %b, %I:%M %p IST")
            if appointment.scheduled_at else "soon")
    await _notify(db, user_id=appointment.host_id, title=f"{name} wants to visit",
                  body=f"{prop.title}, {when}", notification_type="appointment_requested",
                  reference_id=appointment.id, link="/owner?tab=appointments")


@fail_safe
async def appointment_status_changed(db: AsyncSession, appointment: Any, prop: Any, actor_id: UUID) -> None:
    text = APPOINTMENT_STATUS_TEXT.get(appointment.status)
    if not text:
        return
    if actor_id == appointment.host_id:
        recipient, link = appointment.applicant_id, "/dashboard?tab=appointments"
    else:
        recipient, link = appointment.host_id, "/owner?tab=appointments"
    await _notify(db, user_id=recipient, title=f"Your visit {text}", body=prop.title,
                  notification_type="appointment_status_change", reference_id=appointment.id, link=link,
                  idempotency_window_minutes=1)


@fail_safe
async def role_request_decided(db: AsyncSession, request: Any) -> None:
    label = "broker" if request.role == "broker" else request.role.replace("_", " ")
    if request.status == "approved":
        title, body = f"You're now a verified {label}", "You can list properties for your clients."
    else:
        title = f"Your {label} request wasn't approved"
        body = request.decision_note or "Open your profile for details."
    await _notify(db, user_id=request.user_id, title=title, body=body[:200],
                  notification_type="role_request_result", reference_id=request.id,
                  link="/profile", idempotency_window_minutes=1)

