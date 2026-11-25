"""
Administration Router
Protected endpoints for user management, role assignments, account status, and system metrics.
"""
from typing import List, Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles, role_names
from app.modules.users.models import User
from app.modules.administration.schemas import (
    TrafficSnapshot,
    AdminApplicationListItem,
    AdminBillingEventItem,
    AdminUserListItem,
    AdminUserStatusUpdate,
    AdminRoleGrant,
    AdminRoleRequestItem,
    RoleRequestDecision,
    PlatformStatsResponse,
)
from app.modules.administration.service import AdminService
from app.modules.applications.schemas import ApplicationStatus, ApplicationStatusEventResponse
from app.modules.applications.service import ApplicationService
from app.core.dependencies import STAFF_ROLES
from app.core.exceptions import NotFoundException
from app.modules.billing.service import BillingService
from app.modules.users import role_requests

router = APIRouter(prefix="/admin", tags=["Administration & Operations"])

@router.get("/users", response_model=List[AdminUserListItem])
async def list_all_users(
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    return await service.list_users(limit=limit, offset=offset)

@router.patch("/users/{user_id}/status", response_model=AdminUserListItem)
async def update_user_status(
    user_id: UUID,
    data: AdminUserStatusUpdate,
    actor: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    await service.update_user_status(user_id, is_active=data.is_active, actor=actor)
    return await service.get_user_with_roles(user_id)

@router.post("/users/{user_id}/roles", response_model=AdminUserListItem, status_code=status.HTTP_201_CREATED)
async def grant_user_role(
    user_id: UUID,
    data: AdminRoleGrant,
    actor: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Admins grant any non-staff role and moderator; only a super admin grants admin roles."""
    service = AdminService(db)
    await service.grant_user_role(user_id, data.role, actor=actor)
    return await service.get_user_with_roles(user_id)

@router.delete("/users/{user_id}/roles/{role}", response_model=AdminUserListItem)
async def revoke_user_role(
    user_id: UUID,
    role: str,
    actor: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Same rules as granting; the primary role and the last super admin stay."""
    service = AdminService(db)
    await service.revoke_user_role(user_id, role, actor=actor)
    return await service.get_user_with_roles(user_id)

@router.get("/role-requests", response_model=List[AdminRoleRequestItem])
async def list_role_requests(
    status_filter: Optional[Literal["pending", "approved", "declined"]] = Query("pending", alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Waiting broker requests, oldest first (or the decided ones, newest first)."""
    rows = await role_requests.list_for_staff(db, status_filter, limit=limit, offset=offset)
    return [_role_request_item(req, user) for req, user in rows]


@router.post("/role-requests/{request_id}/decision", response_model=AdminRoleRequestItem)
async def decide_role_request(
    request_id: UUID,
    data: RoleRequestDecision,
    actor: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Approve (the role is granted now) or decline with a reason the person sees."""
    req, user = await role_requests.decide(db, request_id, actor, data.approve, data.note)
    user = await AdminService(db).get_user_with_roles(user.id)
    return _role_request_item(req, user)


def _role_request_item(req, user: User) -> AdminRoleRequestItem:
    return AdminRoleRequestItem(
        id=req.id, user_id=user.id, user_name=user.full_name, user_email=user.email,
        user_roles=sorted(role_names(user)), role=req.role, status=req.status, note=req.note,
        decision_note=req.decision_note, created_at=req.created_at, decided_at=req.decided_at,
    )


@router.get("/traffic", response_model=TrafficSnapshot)
async def get_traffic(
    _: User = Depends(require_roles(["admin", "super_admin"])),
):
    """Live traffic over the last minute: requests per second, errors, latency, refusals under
    load, connections in use, open sockets, the busiest routes and each instance. Added up over
    every running instance when Redis is connected, else this instance only (`scope`)."""
    from app.core.metrics import fleet_snapshot

    return await fleet_snapshot()


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_system_stats(
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    return await service.get_platform_stats()


# Payment webhooks (admins only). Every verified delivery is stored before it is applied, so
# one that failed (say, a bug since fixed) can be applied again without waiting for Razorpay.
@router.get("/billing-events", response_model=List[AdminBillingEventItem])
async def list_billing_events(
    status_filter: Optional[Literal["received", "processed", "ignored", "failed"]] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Without a status: the deliveries that need a look (failed, or never finished)."""
    return [AdminBillingEventItem.of(ev) for ev in await BillingService(db).list_events(status_filter, limit)]


@router.post("/billing-events/{event_id}/replay", response_model=AdminBillingEventItem)
async def replay_billing_event(
    event_id: UUID,
    staff: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Apply a failed or unfinished delivery again from its stored payload. Returns the event
    with its new status; a failure comes back as status "failed" with the error."""
    return AdminBillingEventItem.of(await BillingService(db).replay_event(event_id, staff.id))


# Staff (moderators too) can find any application and see its history. Changing the status goes
# through PATCH /applications/{id}/status with a reason, so there's one set of rules.
@router.get("/applications", response_model=List[AdminApplicationListItem])
async def list_applications(
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_roles(list(STAFF_ROLES))),
    db: AsyncSession = Depends(get_db),
):
    return await AdminService(db).list_applications(status=status_filter, q=q, limit=limit, offset=offset)


@router.get("/applications/{application_id}/history", response_model=List[ApplicationStatusEventResponse])
async def application_history(
    application_id: UUID,
    _: User = Depends(require_roles(list(STAFF_ROLES))),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    if not await service.get_by_id(application_id):
        raise NotFoundException("Application not found")
    return await service.history(application_id)
