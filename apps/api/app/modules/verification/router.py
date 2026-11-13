from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.modules.users.models import User
from app.modules.verification.schemas import (
    SubmitVerificationRequest, VerificationResponse, UserTrustScoreResponse
)
from app.modules.verification.service import VerificationService

router = APIRouter(prefix="/verification", tags=["Trust & Verification"])

@router.post("/submit", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
async def submit_verification(
    req: SubmitVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VerificationService(db)
    return await service.submit(current_user.id, req)

@router.get("/status", response_model=UserTrustScoreResponse)
async def get_my_trust_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VerificationService(db)
    return await service.get_trust_status(current_user.id)

@router.patch("/admin/approve/{verification_id}", response_model=VerificationResponse)
async def approve_verification(
    verification_id: UUID,
    _: User = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = VerificationService(db)
    return await service.approve_verification(verification_id)
