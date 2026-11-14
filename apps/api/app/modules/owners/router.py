from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.modules.users.models import User
from app.modules.owners.schemas import OwnerDashboardStats, ApplicantReviewCard, TenantRosterItem
from app.modules.properties.schemas import PropertyResponse
from app.modules.owners.service import OwnerService

router = APIRouter(prefix="/owners", tags=["Owner / Landlord Dashboard"])

@router.get("/dashboard", response_model=OwnerDashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(require_roles(["owner", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = OwnerService(db)
    return await service.get_dashboard_stats(current_user.id)

@router.get("/properties", response_model=List[PropertyResponse])
async def get_owner_properties(
    current_user: User = Depends(require_roles(["owner", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = OwnerService(db)
    return await service.get_owner_properties(current_user.id)

@router.get("/applications", response_model=List[ApplicantReviewCard])
async def get_incoming_applications(
    current_user: User = Depends(require_roles(["owner", "admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = OwnerService(db)
    return await service.get_received_applications(current_user.id)

@router.get("/properties/{property_id}/tenants", response_model=List[TenantRosterItem])
async def get_property_tenant_roster(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = OwnerService(db)
    return await service.get_property_tenants(current_user.id, property_id, is_admin=is_admin)
