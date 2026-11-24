"""
Administration Service
Privileged user management, role granting, account moderation, and platform statistics.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import aliased
from app.modules.applications.models import Application
from app.modules.users.models import User, UserRole
from app.modules.properties.models import Property
from app.modules.matching.models import MutualMatch
from app.modules.verification.models import Verification
from app.modules.moderation.models import ModerationReport
from app.modules.administration.schemas import PlatformStatsResponse
from app.core.exceptions import NotFoundException

class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self, limit: int = 50, offset: int = 0) -> List[User]:
        query = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_applications(
        self, status: Optional[str] = None, q: Optional[str] = None, limit: int = 25, offset: int = 0
    ) -> List[dict]:
        """Applications for staff to find and act on, newest activity first. ``q`` matches the
        listing title or the applicant's name or email."""
        applicant, owner = aliased(User), aliased(User)
        query = (
            select(Application, applicant, Property.title, owner.full_name)
            .join(applicant, applicant.id == Application.applicant_id)
            .join(Property, Property.id == Application.property_id)
            .outerjoin(owner, owner.id == Property.owner_id)
            .order_by(Application.updated_at.desc(), Application.id)
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.where(Application.status == status)
        if q and q.strip():
            term = q.strip()
            query = query.where(or_(
                Property.title.icontains(term, autoescape=True),
                applicant.full_name.icontains(term, autoescape=True),
                applicant.email.icontains(term, autoescape=True),
            ))
        rows = (await self.db.execute(query)).all()
        return [
            {
                "id": app.id, "status": app.status, "applicant_id": app.applicant_id,
                "applicant_name": person.full_name, "applicant_email": person.email,
                "property_id": app.property_id, "property_title": title, "owner_name": owner_name,
                "proposed_rent": app.proposed_rent, "submitted_at": app.submitted_at, "updated_at": app.updated_at,
            }
            for app, person, title, owner_name in rows
        ]

    async def update_user_status(self, user_id: UUID, is_active: bool) -> User:
        query = select(User).where(User.id == user_id)
        user = (await self.db.execute(query)).scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")

        user.is_active = is_active
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def grant_user_role(self, user_id: UUID, role: str) -> UserRole:
        user_query = select(User).where(User.id == user_id)
        user = (await self.db.execute(user_query)).scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")

        existing_q = select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)
        existing = (await self.db.execute(existing_q)).scalar_one_or_none()
        if existing:
            return existing

        user_role = UserRole(user_id=user_id, role=role, is_verified=True)
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)
        return user_role

    async def get_platform_stats(self) -> PlatformStatsResponse:
        total_users = (await self.db.execute(select(func.count(User.id)))).scalar() or 0
        total_properties = (await self.db.execute(select(func.count(Property.id)))).scalar() or 0
        active_listings = (await self.db.execute(
            select(func.count(Property.id)).where(Property.is_active.is_(True), Property.listing_status == "published")
        )).scalar() or 0
        total_matches = (await self.db.execute(
            select(func.count(MutualMatch.id)).where(MutualMatch.status == "matched")
        )).scalar() or 0
        pending_verifications = (await self.db.execute(
            select(func.count(Verification.id)).where(Verification.status == "pending", Verification.method == "manual")
        )).scalar() or 0
        open_reports = (await self.db.execute(
            select(func.count(ModerationReport.id)).where(ModerationReport.status == "open")
        )).scalar() or 0

        return PlatformStatsResponse(
            total_users=total_users,
            total_properties=total_properties,
            total_active_listings=active_listings,
            total_mutual_matches=total_matches,
            pending_verifications=pending_verifications,
            open_moderation_reports=open_reports,
        )
