"""
Unit and Integration Tests for Group Formation, Collective Compatibility,
Pairwise Conflict Analysis, and Wishlist Voting.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.groups.schemas import GroupCreate
from app.modules.groups.service import GroupService
from app.modules.groups.models import Group, GroupMember
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.modules.lifestyle.models import UserDealbreaker
from app.core.exceptions import BadRequestException, ForbiddenException

@pytest.mark.asyncio
async def test_group_creation_assigns_creator_as_leader():
    """When a user creates a group, they are automatically designated as the group leader."""
    creator_id = uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = GroupService(mock_db)

    data = GroupCreate(
        name="Indiranagar 3BHK Seekers",
        description="Looking for flatmates for a spacious flat",
        target_budget_total=60000,
        target_city="Bengaluru",
    )

    created_group = Group(
        id=uuid4(),
        creator_id=creator_id,
        name=data.name,
        target_budget_total=60000,
        target_city="Bengaluru",
        members=[],
        wishlist_items=[],
    )
    service.get_by_id = AsyncMock(return_value=created_group)

    result = await service.create(creator_id, data)
    assert result.name == "Indiranagar 3BHK Seekers"
    assert result.creator_id == creator_id
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_group_duplicate_member_rejected():
    """Adding a member who is already in the group raises BadRequestException."""
    creator_id = uuid4()
    group_id = uuid4()
    mock_db = AsyncMock()
    service = GroupService(mock_db)

    group = Group(id=group_id, creator_id=creator_id, name="Test Group", members=[])
    service.get_by_id = AsyncMock(return_value=group)

    existing_member = GroupMember(id=uuid4(), group_id=group_id, user_id=creator_id)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_member
    mock_db.execute.return_value = mock_res

    with pytest.raises(BadRequestException) as exc_info:
        await service.add_member(group_id, creator_id)
    assert "already a member" in str(exc_info.value.detail).lower()

def _result(value):
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


@pytest.mark.asyncio
async def test_self_join_is_allowed_but_only_as_member():
    """A user may join a listed group themselves; asking for 'leader' still makes them a member."""
    group_id, creator_id, joiner_id = uuid4(), uuid4(), uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = GroupService(mock_db)
    service.get_by_id = AsyncMock(return_value=Group(id=group_id, creator_id=creator_id, name="G", members=[]))

    mock_db.execute.side_effect = [_result(None)]  # not yet a member
    member = await service.add_member(group_id, joiner_id, requester_id=joiner_id, role="leader")
    assert member.user_id == joiner_id
    assert member.role == "member"


@pytest.mark.asyncio
async def test_plain_member_cannot_add_other_users():
    """Only the creator, a leader or an admin may add someone else."""
    group_id, creator_id, member_id = uuid4(), uuid4(), uuid4()
    mock_db = AsyncMock()
    service = GroupService(mock_db)
    service.get_by_id = AsyncMock(return_value=Group(id=group_id, creator_id=creator_id, name="G", members=[]))

    mock_db.execute.side_effect = [_result(None)]  # requester is not a leader
    with pytest.raises(ForbiddenException):
        await service.add_member(group_id, uuid4(), requester_id=member_id)


@pytest.mark.asyncio
async def test_unknown_member_role_rejected():
    group_id, creator_id = uuid4(), uuid4()
    service = GroupService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=Group(id=group_id, creator_id=creator_id, name="G", members=[]))
    with pytest.raises(BadRequestException):
        await service.add_member(group_id, uuid4(), requester_id=creator_id, role="owner")


@pytest.mark.asyncio
async def test_group_collective_compatibility_with_dealbreaker_penalty():
    """
    A high average must NOT hide one severe dealbreaker between two members.
    Member A and Member B have a strict smoking dealbreaker conflict.
    Group score must be penalized and flagged.
    """
    group_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    user_c = uuid4()

    mock_db = AsyncMock()
    service = GroupService(mock_db)

    member_a = GroupMember(user_id=user_a)
    member_b = GroupMember(user_id=user_b)
    member_c = GroupMember(user_id=user_c)

    group = Group(
        id=group_id,
        creator_id=user_a,
        name="Tech Trio",
        members=[member_a, member_b, member_c],
    )
    service.get_by_id = AsyncMock(return_value=group)

    # User A: Non-smoker, strict
    user_a_obj = User(id=user_a, full_name="Alice (Non-Smoker)")
    prof_a = Profile(user_id=user_a, budget_min=15000, budget_max=25000, lifestyle_traits={"smoking": "never", "diet_preference": "pure_veg"})

    # User B: Smoker allowed inside
    user_b_obj = User(id=user_b, full_name="Bob (Smoker)")
    prof_b = Profile(user_id=user_b, budget_min=15000, budget_max=25000, lifestyle_traits={"smoking": "permitted", "diet_preference": "non_veg"})

    # User C: Neutral
    user_c_obj = User(id=user_c, full_name="Charlie (Flexible)")
    prof_c = Profile(user_id=user_c, budget_min=15000, budget_max=25000, lifestyle_traits={"smoking": "never", "diet_preference": "omnivore"})

    dealbreaker_a = UserDealbreaker(user_id=user_a, rule_key="no_smoking_inside", is_strict=True, expected_value="never")

    mock_users_res = MagicMock()
    mock_users_res.scalars.return_value.all.return_value = [user_a_obj, user_b_obj, user_c_obj]

    mock_profs_res = MagicMock()
    mock_profs_res.scalars.return_value.all.return_value = [prof_a, prof_b, prof_c]

    mock_dbs_res = MagicMock()
    mock_dbs_res.scalars.return_value.all.return_value = [dealbreaker_a]

    mock_db.execute.side_effect = [mock_users_res, mock_profs_res, mock_dbs_res]

    res = await service.compute_group_compatibility(group_id)

    # Verify dealbreaker was triggered
    assert res.dealbreakers_cleared is False
    assert res.collective_score <= 30.0
    assert len(res.group_conflicts) >= 1
    assert any("Alice" in c and "Bob" in c for c in res.group_conflicts)

@pytest.mark.asyncio
async def test_wishlist_voting():
    """Members can cast upvotes or downvotes on shared properties."""
    group_id = uuid4()
    prop_id = uuid4()
    voter_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = GroupService(mock_db)

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = GroupMember(group_id=group_id, user_id=voter_id)

    mock_empty = MagicMock()
    mock_empty.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_member_res, mock_empty]

    item = await service.vote_wishlist(group_id, prop_id, voter_id, vote="up")
    assert item.votes[str(voter_id)] == "up"
    assert mock_db.commit.called
