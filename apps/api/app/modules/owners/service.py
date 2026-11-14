from decimal import Decimal
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.modules.properties.models import Property
from app.modules.applications.models import Application
from app.modules.users.models import User
from app.modules.profiles.models import Profile
from app.modules.tenants.models import TenantMembership
from app.modules.properties.models import Room, Bed
from app.modules.owners.schemas import OwnerDashboardStats, ApplicantReviewCard, TenantRosterItem
from app.core.exceptions import NotFoundException, ForbiddenException
from app.modules.applications.schemas import ApplicationResponse
from app.modules.properties.service import PropertyService

class OwnerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_stats(self, owner_id: UUID) -> OwnerDashboardStats:
        # 1. Properties owned
        props_query = select(Property).where(Property.owner_id == owner_id)
        props = (await self.db.execute(props_query)).scalars().all()

        total_properties = len(props)
        active_listings = sum(1 for p in props if p.is_active)
        estimated_revenue = sum(p.monthly_rent for p in props if p.is_active)

        # 2. Applications received
        prop_ids = [p.id for p in props]
        pending_apps = 0
        if prop_ids:
            app_query = select(func.count(Application.id)).where(
                Application.property_id.in_(prop_ids),
                Application.status == "submitted"
            )
            pending_apps = (await self.db.execute(app_query)).scalar() or 0

        return OwnerDashboardStats(
            total_properties=total_properties,
            active_listings=active_listings,
            pending_applications=pending_apps,
            total_inquiries=pending_apps * 3,
            estimated_monthly_revenue=Decimal(str(estimated_revenue)),
        )

    async def get_received_applications(self, owner_id: UUID) -> List[ApplicantReviewCard]:
        query = (
            select(Application, User, Profile, Property)
            .join(Property, Application.property_id == Property.id)
            .join(User, Application.applicant_id == User.id)
            .outerjoin(Profile, User.id == Profile.user_id)
            .where(Property.owner_id == owner_id)
            .order_by(Application.submitted_at.desc())
        )
        result = await self.db.execute(query)
        rows = result.all()

        cards = []
        for app, user, profile, prop in rows:
            cards.append(ApplicantReviewCard(
                application=ApplicationResponse.model_validate(app),
                applicant_name=user.full_name,
                applicant_email=user.email,
                applicant_occupation=profile.occupation if profile else None,
                applicant_avatar=profile.avatar_url if profile else None,
                is_verified=user.is_verified,
                property_title=prop.title,
            ))
        return cards

    async def get_property_tenants(self, owner_id: UUID, property_id: UUID, is_admin: bool = False) -> List[TenantRosterItem]:
        prop_query = select(Property).where(Property.id == property_id)
        prop = (await self.db.execute(prop_query)).scalar_one_or_none()
        if not prop:
            raise NotFoundException("Property not found")
        if prop.owner_id != owner_id and not is_admin:
            raise ForbiddenException("Access denied to tenant roster for this property")

        query = (
            select(TenantMembership, User, Room, Bed)
            .join(User, TenantMembership.tenant_id == User.id)
            .outerjoin(Room, TenantMembership.room_id == Room.id)
            .outerjoin(Bed, TenantMembership.bed_id == Bed.id)
            .where(TenantMembership.property_id == property_id)
            .where(TenantMembership.status == "active")
        )
        result = await self.db.execute(query)
        rows = result.all()

        roster = []
        for membership, user, room, bed in rows:
            roster.append(TenantRosterItem(
                membership_id=str(membership.id),
                tenant_id=str(user.id),
                tenant_name=user.full_name,
                tenant_email=user.email,
                room_name=room.room_name if room else None,
                bed_identifier=bed.bed_identifier if bed else None,
                monthly_rent=membership.monthly_rent,
                status=membership.status,
                is_primary_tenant=membership.is_primary_tenant,
            ))
        return roster

    async def get_owner_properties(self, owner_id: UUID) -> List[Dict[str, Any]]:
        query = (
            select(Property)
            .options(
                selectinload(Property.rooms).selectinload(Room.beds),
                selectinload(Property.amenities),
            )
            .where(Property.owner_id == owner_id)
            .order_by(Property.created_at.desc())
        )
        result = await self.db.execute(query)
        props = result.scalars().all()
        prop_service = PropertyService(self.db)
        return [prop_service._format_property_response(p, viewer_id=owner_id, is_admin=False) for p in props]

