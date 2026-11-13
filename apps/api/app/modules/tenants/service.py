"""
Tenants Service
Manages active leases, household tenancies, and tenant-posted flatmate vacancies.
"""
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.tenants.models import TenantMembership, ExistingTenantVacancy
from app.modules.tenants.schemas import ExistingTenantVacancyCreate
from app.core.exceptions import NotFoundException, ForbiddenException

class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_memberships(self, tenant_id: UUID) -> List[TenantMembership]:
        query = (
            select(TenantMembership)
            .where(TenantMembership.tenant_id == tenant_id)
            .order_by(TenantMembership.created_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_vacancy(self, tenant_id: UUID, data: ExistingTenantVacancyCreate) -> ExistingTenantVacancy:
        # Verify tenant has an active tenancy on this property
        membership_query = select(TenantMembership).where(
            TenantMembership.property_id == data.property_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active"
        )
        membership = (await self.db.execute(membership_query)).scalar_one_or_none()
        if not membership:
            raise ForbiddenException("You must be an active tenant of this property to list a vacancy")

        vacancy = ExistingTenantVacancy(
            property_id=data.property_id,
            room_id=data.room_id,
            posted_by_tenant_id=tenant_id,
            title=data.title,
            description=data.description,
            vacant_from=data.vacant_from,
            expected_rent=data.expected_rent,
            deposit_required=data.deposit_required,
            preferred_gender=data.preferred_gender,
            is_active=True,
        )
        self.db.add(vacancy)
        await self.db.commit()
        await self.db.refresh(vacancy)
        return vacancy

    async def list_vacancies(
        self,
        preferred_gender: Optional[str] = None,
        max_rent: Optional[Decimal] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[ExistingTenantVacancy]:
        query = select(ExistingTenantVacancy).where(ExistingTenantVacancy.is_active.is_(True))
        if preferred_gender and preferred_gender != "any":
            query = query.where(ExistingTenantVacancy.preferred_gender.in_([preferred_gender, "any"]))
        if max_rent is not None:
            query = query.where(ExistingTenantVacancy.expected_rent <= max_rent)

        query = query.order_by(ExistingTenantVacancy.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_vacancy_by_id(self, vacancy_id: UUID) -> Optional[ExistingTenantVacancy]:
        query = select(ExistingTenantVacancy).where(ExistingTenantVacancy.id == vacancy_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def close_vacancy(self, vacancy_id: UUID, user_id: UUID, is_admin: bool = False) -> ExistingTenantVacancy:
        vacancy = await self.get_vacancy_by_id(vacancy_id)
        if not vacancy:
            raise NotFoundException("Vacancy listing not found")
        if vacancy.posted_by_tenant_id != user_id and not is_admin:
            raise ForbiddenException("Only the poster or an admin can close this vacancy")

        vacancy.is_active = False
        await self.db.commit()
        await self.db.refresh(vacancy)
        return vacancy
