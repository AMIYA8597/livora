from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, has_admin_role
from app.modules.users.models import User
from app.modules.profiles.schemas import (
    ProfileResponse,
    ProfileUpdate,
    LifestyleTraitsSchema,
    PrivacySettingsUpdate,
    PrivacySettingsResponse,
)
from app.modules.profiles.service import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    is_admin = has_admin_role(current_user)
    return await service.get_profile_with_privacy(
        requester_id=current_user.id,
        target_user_id=current_user.id,
        is_admin=is_admin,
    )

@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    await service.update(current_user.id, data)
    is_admin = has_admin_role(current_user)
    return await service.get_profile_with_privacy(
        requester_id=current_user.id,
        target_user_id=current_user.id,
        is_admin=is_admin,
    )

@router.get("/me/privacy", response_model=PrivacySettingsResponse)
async def get_my_privacy_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.get_privacy_settings(current_user.id)

@router.put("/me/privacy", response_model=PrivacySettingsResponse)
async def update_my_privacy_settings(
    data: PrivacySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    return await service.update_privacy_settings(current_user.id, data)

@router.post("/me/quiz", response_model=ProfileResponse)
async def submit_quiz(
    data: LifestyleTraitsSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ProfileService(db)
    await service.submit_lifestyle_quiz(current_user.id, data)
    is_admin = has_admin_role(current_user)
    return await service.get_profile_with_privacy(
        requester_id=current_user.id,
        target_user_id=current_user.id,
        is_admin=is_admin,
    )

@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile_by_user_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = ProfileService(db)
    is_admin = has_admin_role(current_user)
    return await service.get_profile_with_privacy(
        requester_id=current_user.id,
        target_user_id=user_id,
        is_admin=is_admin,
    )
