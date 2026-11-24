"""
Administration Service
Privileged user management, role granting, account moderation, and platform statistics.
"""
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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
