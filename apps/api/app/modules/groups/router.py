from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_user, is_staff, has_admin_role
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.groups.models import Group
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

def group_view(group: Group, viewer: Optional[User]) -> GroupResponse:
    """Who's in a group (and how they voted) is for the group itself; the public sees the count."""
    member_ids = {m.user_id for m in group.members}
    is_member = viewer is not None and viewer.id in member_ids
    insider = is_member or (viewer is not None and (viewer.id == group.creator_id or is_staff(viewer)))
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        target_budget_total=group.target_budget_total,
        target_city=group.target_city,
        target_move_in=group.target_move_in,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=len(member_ids),
        is_member=is_member,
        creator_id=group.creator_id if insider else None,
        members=[GroupMemberResponse.model_validate(m) for m in group.members] if insider else [],
        wishlist_items=[GroupWishlistItemResponse.model_validate(w) for w in group.wishlist_items] if insider else [],
    )


@router.get("/", response_model=List[GroupResponse])
async def list_groups(
    city: Optional[str] = Query(None, max_length=100),
    viewer: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return [group_view(g, viewer) for g in await service.list_groups(city=city)]

@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    return group_view(await service.create(current_user.id, data), current_user)

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: UUID,
    viewer: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    service = GroupService(db)
    group = await service.get_by_id(group_id)
    if not group:
        raise NotFoundException("Group not found")
    return group_view(group, viewer)

@router.post("/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: UUID,
    data: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = has_admin_role(current_user)
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
    is_admin = has_admin_role(current_user)
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
    group = await service.get_by_id(group_id)
    if not group:
        raise NotFoundException("Group not found")
    # Scores name every member and compare their lifestyles: members and staff only.
    if current_user.id not in {m.user_id for m in group.members} and not is_staff(current_user):
        raise ForbiddenException("Only the group's members can see its compatibility")
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
