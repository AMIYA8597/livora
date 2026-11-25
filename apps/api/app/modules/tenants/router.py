"""
Tenants Router
REST endpoints for tenant memberships and roommate replacement vacancy postings.
"""
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, has_admin_role
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.tenants.schemas import (
    TenantMembershipResponse,
    ExistingTenantVacancyCreate,
    ExistingTenantVacancyResponse,
)
from app.modules.tenants.service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants & Roommate Vacancies"])

@router.get("/my-memberships", response_model=List[TenantMembershipResponse])
async def get_my_memberships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    return await service.get_my_memberships(current_user.id)

@router.post("/vacancies", response_model=ExistingTenantVacancyResponse, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    data: ExistingTenantVacancyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    return await service.create_vacancy(current_user.id, data)

@router.get("/vacancies", response_model=List[ExistingTenantVacancyResponse])
async def list_vacancies(
    preferred_gender: Optional[str] = Query(None, description="any, female_only, male_only"),
    max_rent: Optional[Decimal] = Query(None, description="Maximum rent in INR"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    return await service.list_vacancies(preferred_gender=preferred_gender, max_rent=max_rent, limit=limit, offset=offset)

@router.get("/vacancies/{vacancy_id}", response_model=ExistingTenantVacancyResponse)
async def get_vacancy(
    vacancy_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    vacancy = await service.get_vacancy_by_id(vacancy_id)
    if not vacancy:
        raise NotFoundException("Vacancy listing not found")
    return vacancy

@router.delete("/vacancies/{vacancy_id}", response_model=ExistingTenantVacancyResponse)
async def close_vacancy(
    vacancy_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = has_admin_role(current_user)
    service = TenantService(db)
    return await service.close_vacancy(vacancy_id, current_user.id, is_admin=is_admin)
