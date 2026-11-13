from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.verification.models import Verification
from app.modules.users.models import User
from app.modules.verification.schemas import SubmitVerificationRequest, UserTrustScoreResponse
from app.core.exceptions import NotFoundException

class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, user_id: UUID, req: SubmitVerificationRequest) -> Verification:
        v = Verification(
            user_id=user_id,
            verification_type=req.verification_type,
            document_url=req.document_url,
            status="pending",
        )
        self.db.add(v)
        await self.db.commit()
        await self.db.refresh(v)
        return v

    async def get_trust_status(self, user_id: UUID) -> UserTrustScoreResponse:
        query = select(Verification).where(
            Verification.user_id == user_id,
            Verification.status == "approved"
        )
        result = await self.db.execute(query)
        approved = result.scalars().all()

        score = 20 # Base registration trust
        badges = []
        for a in approved:
            score += a.trust_score_bonus
            badges.append(a.verification_type)

        score = min(100, score)
        return UserTrustScoreResponse(
            user_id=user_id,
            total_trust_score=score,
            badges=badges,
            is_fully_verified=score >= 70,
        )

    async def approve_verification(self, verification_id: UUID) -> Verification:
        query = select(Verification).where(Verification.id == verification_id)
        v = (await self.db.execute(query)).scalar_one_or_none()
        if not v:
            raise NotFoundException("Verification request not found")

        v.status = "approved"
        v.verified_at = datetime.now(timezone.utc)

        # Update user.is_verified if high enough
        user_query = select(User).where(User.id == v.user_id)
        user = (await self.db.execute(user_query)).scalar_one()
        user.is_verified = True

        await self.db.commit()
        await self.db.refresh(v)
        return v
