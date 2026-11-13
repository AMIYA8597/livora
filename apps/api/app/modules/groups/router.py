from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.groups.schemas import (
    GroupResponse,
    GroupCreate,
    GroupMemberResponse,
    GroupWishlistItemResponse,
    WishlistVoteRequest,
    AddMemberRequest,
    GroupCompatibilityResponse,
)
from app.modules.groups.service import GroupService

router = APIRouter(prefix="/groups", tags=["Group Matching & Flatsharing"])

@router.get("/", response_model=List[GroupResponse])
async def list_groups(
    city: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.list_groups(city=city)

@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.create(current_user.id, data)

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    group = await service.get_by_id(group_id)
    if not group:
        raise NotFoundException("Group not found")
    return group

@router.post("/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: UUID,
    data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = GroupService(db)
    return await service.add_member(
        group_id, data.user_id, requester_id=current_user.id, role=data.role, is_admin=is_admin
    )

@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = GroupService(db)
    await service.remove_member(group_id, user_id, requester_id=current_user.id, is_admin=is_admin)
    return None

@router.get("/{group_id}/compatibility", response_model=GroupCompatibilityResponse)
async def get_group_compatibility(
    group_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.compute_group_compatibility(group_id)

@router.post("/{group_id}/wishlist/{property_id}/vote", response_model=GroupWishlistItemResponse)
async def vote_property_wishlist(
    group_id: UUID,
    property_id: UUID,
    data: WishlistVoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return await service.vote_wishlist(group_id, property_id, current_user.id, data.vote)
