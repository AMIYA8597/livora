"""
Lifestyle Router
REST endpoints for 10-dimension questionnaire and dealbreaker management.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_user, has_admin_role
from app.modules.users.models import User, UserPrivacySetting
from app.modules.lifestyle.schemas import (
    LifestyleCreateOrUpdate,
    LifestyleResponse,
    DealbreakerCreate,
    DealbreakerResponse,
)
from app.modules.lifestyle.service import LifestyleService
from app.core.exceptions import NotFoundException, ForbiddenException

router = APIRouter(prefix="/lifestyle", tags=["Lifestyle & Dealbreakers"])

@router.get("/me", response_model=LifestyleResponse)
async def get_my_lifestyle(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = LifestyleService(db)
    profile = await service.get_by_user_id(current_user.id)
    if not profile:
        raise NotFoundException("Lifestyle profile not yet completed")
    return profile

@router.put("/me", response_model=LifestyleResponse)
async def update_my_lifestyle(
    data: LifestyleCreateOrUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = LifestyleService(db)
    return await service.upsert_lifestyle(current_user.id, data)

@router.get("/dealbreakers", response_model=List[DealbreakerResponse])
async def get_my_dealbreakers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = LifestyleService(db)
    return await service.get_dealbreakers(current_user.id)

@router.post("/dealbreakers", response_model=DealbreakerResponse, status_code=status.HTTP_201_CREATED)
async def add_dealbreaker(
    data: DealbreakerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = LifestyleService(db)
    return await service.add_dealbreaker(current_user.id, data)

@router.delete("/dealbreakers/{dealbreaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dealbreaker(
    dealbreaker_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = LifestyleService(db)
    await service.delete_dealbreaker(current_user.id, dealbreaker_id)
    return None

@router.get("/{user_id}", response_model=LifestyleResponse)
async def get_user_lifestyle(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check privacy settings of the requested user
    if current_user.id != user_id and not has_admin_role(current_user):
        privacy_query = select(UserPrivacySetting).where(UserPrivacySetting.user_id == user_id)
        privacy_res = await db.execute(privacy_query)
        privacy = privacy_res.scalar_one_or_none()
        if privacy:
            if privacy.profile_visibility == "private":
                raise ForbiddenException("User profile is private")
            elif privacy.profile_visibility == "matched_only":
                from app.modules.matching.models import MutualMatch
                from sqlalchemy import or_, and_
                match_query = select(MutualMatch).where(
                    or_(
                        and_(MutualMatch.user_one_id == current_user.id, MutualMatch.user_two_id == user_id),
                        and_(MutualMatch.user_one_id == user_id, MutualMatch.user_two_id == current_user.id)
                    ),
                    MutualMatch.status == "matched"
                )
                match_res = await db.execute(match_query)
                if not match_res.scalar_one_or_none():
                    raise ForbiddenException("This profile is only visible to mutual matches")

    service = LifestyleService(db)
    profile = await service.get_by_user_id(user_id)
    if not profile:
        raise NotFoundException("Lifestyle profile not found for user")
    return profile
