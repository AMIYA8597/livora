"""
Moderation & Safety Router
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.modules.users.models import User
from app.modules.moderation.schemas import (
    ReportCreate,
    ReportResponse,
    ReportReviewRequest,
    BlockUserResponse,
)
from app.modules.moderation.service import ModerationService

router = APIRouter(prefix="/moderation", tags=["Moderation & Safety"])

@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_moderation_report(
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    return await service.submit_report(current_user.id, data)

@router.get("/reports", response_model=List[ReportResponse])
async def list_moderation_reports(
    status: Optional[str] = Query(None),
    _: User = Depends(require_roles(["moderator", "admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    return await service.list_reports(status=status)

@router.patch("/reports/{report_id}", response_model=ReportResponse)
async def review_moderation_report(
    report_id: UUID,
    review: ReportReviewRequest,
    _: User = Depends(require_roles(["moderator", "admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    return await service.review_report(report_id, review)

@router.post("/blocks/{blocked_user_id}", response_model=BlockUserResponse, status_code=status.HTTP_201_CREATED)
async def block_user(
    blocked_user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    return await service.block_user(current_user.id, blocked_user_id)

@router.delete("/blocks/{blocked_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_user(
    blocked_user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    await service.unblock_user(current_user.id, blocked_user_id)
    return None

@router.get("/blocks", response_model=List[BlockUserResponse])
async def list_my_blocked_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ModerationService(db)
    return await service.get_blocked_users(current_user.id)
