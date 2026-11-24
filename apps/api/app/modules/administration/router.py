"""
Administration Router
Protected endpoints for user management, role assignments, account status, and system metrics.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.modules.users.models import User
from app.modules.administration.schemas import (
    AdminApplicationListItem,
    AdminUserListItem,
    AdminUserStatusUpdate,
    AdminRoleGrant,
    PlatformStatsResponse,
)
from app.modules.administration.service import AdminService
from app.modules.applications.schemas import ApplicationStatus, ApplicationStatusEventResponse
from app.modules.applications.service import ApplicationService
from app.core.dependencies import STAFF_ROLES
from app.core.exceptions import NotFoundException

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
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    return await service.update_user_status(user_id, is_active=data.is_active)

@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def grant_user_role(
    user_id: UUID,
    data: AdminRoleGrant,
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    return await service.grant_user_role(user_id, data.role)

@router.get("/stats", response_model=PlatformStatsResponse)
async def get_system_stats(
    _: User = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = AdminService(db)
    return await service.get_platform_stats()


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
