"""
Moderation Service
Handles report submissions, user blocking, and administrative review actions.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.moderation.models import ModerationReport, UserBlock
from app.modules.moderation.schemas import ReportCreate, ReportReviewRequest
from app.core.exceptions import NotFoundException, BadRequestException, ConflictException

class ModerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_report(self, reporter_id: UUID, data: ReportCreate) -> ModerationReport:
        if data.target_type == "user" and data.target_id == reporter_id:
            raise BadRequestException("Cannot report yourself")

        report = ModerationReport(
            reporter_id=reporter_id,
            target_type=data.target_type,
            target_id=data.target_id,
            reason=data.reason,
            description=data.description,
            status="open",
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_reports(self, status: Optional[str] = None) -> List[ModerationReport]:
        query = select(ModerationReport)
        if status:
            query = query.where(ModerationReport.status == status)
        query = query.order_by(ModerationReport.created_at.desc()).limit(100)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def review_report(self, report_id: UUID, review: ReportReviewRequest) -> ModerationReport:
        query = select(ModerationReport).where(ModerationReport.id == report_id)
        report = (await self.db.execute(query)).scalar_one_or_none()
        if not report:
            raise NotFoundException("Moderation report not found")

        report.status = review.status
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def block_user(self, user_id: UUID, blocked_user_id: UUID) -> UserBlock:
        if user_id == blocked_user_id:
            raise BadRequestException("Cannot block yourself")

        existing_q = select(UserBlock).where(
            UserBlock.user_id == user_id,
            UserBlock.blocked_user_id == blocked_user_id
        )
        if (await self.db.execute(existing_q)).scalar_one_or_none():
            raise ConflictException("User is already blocked")

        block = UserBlock(user_id=user_id, blocked_user_id=blocked_user_id)
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        return block

    async def unblock_user(self, user_id: UUID, blocked_user_id: UUID) -> bool:
        query = select(UserBlock).where(
            UserBlock.user_id == user_id,
            UserBlock.blocked_user_id == blocked_user_id
        )
        block = (await self.db.execute(query)).scalar_one_or_none()
        if not block:
            raise NotFoundException("Block record not found")

        await self.db.delete(block)
        await self.db.commit()
        return True

    async def get_blocked_users(self, user_id: UUID) -> List[UserBlock]:
        query = select(UserBlock).where(UserBlock.user_id == user_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
