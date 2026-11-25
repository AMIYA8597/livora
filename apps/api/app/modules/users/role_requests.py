"""
Asking for a role that staff grant after a check (brokers), and staff deciding.

A broker must be someone Flatmate has looked at: seekers come here expecting no surprise
brokerage, so a broker badge has to mean something. The person asks from their profile with a
short note (agency, RERA number, city); an admin approves (the role is granted at once) or
declines with a reason the person sees.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import role_names
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.core.roles import REQUESTABLE_ROLES
from app.modules.users.models import RoleRequest, User

ROLE_LABELS = {"broker": "broker"}


async def create_request(db: AsyncSession, user: User, role: str, note: Optional[str]) -> RoleRequest:
    if role not in REQUESTABLE_ROLES:
        raise BadRequestException("That role can't be requested")
    if role in role_names(user):
        raise BadRequestException("You already have that role")
    open_q = select(RoleRequest).where(
        RoleRequest.user_id == user.id, RoleRequest.role == role, RoleRequest.status == "pending"
    )
    if (await db.execute(open_q)).scalar_one_or_none():
        raise ConflictException("Your request is already waiting for a review")
    req = RoleRequest(user_id=user.id, role=role, note=(note or "").strip() or None)
    db.add(req)
    try:
        await db.commit()
    except IntegrityError:  # a second tab won the race: same answer as above
        await db.rollback()
        raise ConflictException("Your request is already waiting for a review")
    await db.refresh(req)
    return req


async def list_mine(db: AsyncSession, user: User) -> List[RoleRequest]:
    q = select(RoleRequest).where(RoleRequest.user_id == user.id).order_by(RoleRequest.created_at.desc())
    return list((await db.execute(q)).scalars().all())


async def list_for_staff(
    db: AsyncSession, status: Optional[str], limit: int = 50, offset: int = 0
) -> List[Tuple[RoleRequest, User]]:
    q = select(RoleRequest, User).join(User, User.id == RoleRequest.user_id)
    if status:
        q = q.where(RoleRequest.status == status)
    # Oldest first while waiting (first come, first served); newest first in the history.
    order = RoleRequest.created_at.asc() if status == "pending" else RoleRequest.created_at.desc()
    q = q.order_by(order).limit(limit).offset(offset)
    return [(r, u) for r, u in (await db.execute(q)).all()]


async def decide(
    db: AsyncSession, request_id: UUID, actor: User, approve: bool, note: Optional[str]
) -> Tuple[RoleRequest, User]:
    from app.modules.administration.service import AdminService
    from app.modules.notifications import events

    req = (await db.execute(
        select(RoleRequest).where(RoleRequest.id == request_id).with_for_update()
    )).scalar_one_or_none()
    if req is None:
        raise NotFoundException("Request not found")
    if req.status != "pending":
        raise ConflictException("This request has already been decided")
    note = (note or "").strip() or None
    if not approve and not note:
        raise BadRequestException("Say why, so the person knows what to fix")

    # Record the decision first, so it and the role grant commit together while the row is
    # still locked: two staff deciding at once can't leave a granted role on a declined request.
    req.status = "approved" if approve else "declined"
    req.decision_note = note
    req.decided_by = actor.id
    req.decided_at = datetime.now(timezone.utc)
    try:
        if approve:
            # The same checks as a manual grant (who may grant what, and to whom).
            await AdminService(db).grant_user_role(req.user_id, req.role, actor=actor)
        await db.commit()  # the grant returns early, uncommitted, when the role is already held
    except Exception:
        await db.rollback()
        raise
    await db.refresh(req)
    user = await db.get(User, req.user_id)
    assert user is not None  # the FK cascades: a request never outlives its person
    await events.role_request_decided(db, req)
    return req, user
