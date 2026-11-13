from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.matching.schemas import (
    FlatmateMatchResponse,
    ScoreBreakdownSchema,
    MatchInteractionRequest,
    MatchInteractionResponse,
    MutualMatchItemResponse,
)
from app.modules.matching.service import MatchingService

router = APIRouter(prefix="/matching", tags=["Matching Engine"])

@router.get("/recommendations", response_model=List[FlatmateMatchResponse])
async def get_match_recommendations(
    limit: int = Query(10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MatchingService(db)
    return await service.get_user_recommendations(current_user.id, limit=limit)

@router.get("/compatibility/{target_user_id}", response_model=ScoreBreakdownSchema)
async def get_compatibility_score(
    target_user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MatchingService(db)
    return await service.get_pairwise_score(current_user.id, target_user_id)

@router.post("/interactions", response_model=MatchInteractionResponse, status_code=status.HTTP_200_OK)
async def record_user_interaction(
    data: MatchInteractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MatchingService(db)
    return await service.record_interaction(
        user_id=current_user.id,
        target_user_id=data.target_user_id,
        action=data.action
    )

@router.get("/matches", response_model=List[MutualMatchItemResponse])
async def get_my_mutual_matches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MatchingService(db)
    return await service.get_mutual_matches(current_user.id)
