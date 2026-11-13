"""
Unit and Integration Tests for User Profiles, 10-Dimension Lifestyle, Dealbreakers, and Privacy Rules.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.profiles.service import ProfileService
from app.modules.lifestyle.schemas import LifestyleCreateOrUpdate, DealbreakerCreate
from app.modules.lifestyle.service import compute_lifestyle_profile_vector, LifestyleService
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting
from app.core.exceptions import ForbiddenException

def test_lifestyle_vector_embedding_10_dimensions():
    """Verify 10-dimension lifestyle questionnaire produces valid normalized 64-dim vector."""
    lifestyle = LifestyleCreateOrUpdate(
        sleep_schedule="early_bird",
        wake_time_typical="06:00",
        sleep_time_typical="22:30",
        work_arrangement="hybrid",
        cleanliness_level=5,
        chore_philosophy="shared_roster",
        noise_tolerance="quiet_library",
        instrument_or_music=False,
        lighting_preference="pitch_black",
        guests_policy="rarely",
        social_battery="introverted",
        diet_preference="pure_veg",
        non_veg_cooking_allowed=False,
        cooks_at_home="daily",
        smoking="never",
        drinking="teetotaler",
        pet_preference="no_pets",
        custom_notes="Prefer early risers and peaceful household."
    )
    vec = compute_lifestyle_profile_vector(lifestyle)
    assert len(vec) == 64
    # Unit length check (L2 norm)
    norm = sum(x * x for x in vec)
    assert abs(norm - 1.0) < 0.001

@pytest.mark.asyncio
async def test_dealbreaker_creation_and_retrieval():
    """Verify dealbreaker models and service operations."""
    user_id = uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # Mock empty result on initial call or return dealbreaker
    service = LifestyleService(mock_db)

    dealbreaker_input = DealbreakerCreate(
        rule_key="pure_veg_kitchen_only",
        is_strict=True,
        expected_value="pure_veg"
    )

    result = await service.add_dealbreaker(user_id, dealbreaker_input)
    assert result.user_id == user_id
    assert result.rule_key == "pure_veg_kitchen_only"
    assert result.is_strict is True
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_privacy_phone_masking_for_strangers():
    """Strangers viewing a profile must see masked phone number if show_phone_publicly is False."""
    owner_id = uuid4()
    viewer_id = uuid4()

    mock_db = AsyncMock()

    profile = Profile(
        id=uuid4(),
        user_id=owner_id,
        display_name="Rahul Verma",
        education_institute="IIT Delhi",
        education_degree="B.Tech Computer Science",
        company_name="Zomato",
        designation="Software Engineer",
        budget_min=15000,
        budget_max=25000,
        lifestyle_vector=[0.0] * 64,
        lifestyle_traits={},
        preferred_locations=["Indiranagar", "Koramangala"]
    )

    target_user = User(
        id=owner_id,
        email="rahul@example.com",
        hashed_password="hash",
        full_name="Rahul Verma",
        phone_number="+919876543210"
    )

    privacy = UserPrivacySetting(
        id=uuid4(),
        user_id=owner_id,
        show_phone_publicly=False,
        show_exact_location=False,
        allow_direct_messages=True,
        profile_visibility="public"
    )

    service = ProfileService(mock_db)
    service.get_by_user_id = AsyncMock(return_value=profile)
    service.get_privacy_settings = AsyncMock(return_value=privacy)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = mock_user_res

    res = await service.get_profile_with_privacy(requester_id=viewer_id, target_user_id=owner_id, is_admin=False)
    assert res.phone_number == "+91******10"
    assert res.display_name == "Rahul Verma"
    assert res.education_institute == "IIT Delhi"
    assert res.company_name == "Zomato"

@pytest.mark.asyncio
async def test_privacy_unmasked_phone_for_owner_or_admin():
    """Owner and admin should see the raw unmasked phone number."""
    owner_id = uuid4()
    admin_id = uuid4()

    mock_db = AsyncMock()
    profile = Profile(
        id=uuid4(),
        user_id=owner_id,
        display_name="Priya Sharma",
        budget_min=10000,
        budget_max=20000,
        lifestyle_vector=[0.0] * 64,
        lifestyle_traits={},
        preferred_locations=[]
    )
    target_user = User(
        id=owner_id,
        email="priya@example.com",
        hashed_password="hash",
        full_name="Priya Sharma",
        phone_number="+919988776655"
    )
    privacy = UserPrivacySetting(
        id=uuid4(),
        user_id=owner_id,
        show_phone_publicly=False,
        profile_visibility="public"
    )

    service = ProfileService(mock_db)
    service.get_by_user_id = AsyncMock(return_value=profile)
    service.get_privacy_settings = AsyncMock(return_value=privacy)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = mock_user_res

    # 1. Owner self view
    res_owner = await service.get_profile_with_privacy(requester_id=owner_id, target_user_id=owner_id, is_admin=False)
    assert res_owner.phone_number == "+919988776655"

    # 2. Admin view
    res_admin = await service.get_profile_with_privacy(requester_id=admin_id, target_user_id=owner_id, is_admin=True)
    assert res_admin.phone_number == "+919988776655"

@pytest.mark.asyncio
async def test_privacy_strict_visibility_private():
    """Private profile must raise ForbiddenException for non-owners and non-admins."""
    owner_id = uuid4()
    viewer_id = uuid4()

    mock_db = AsyncMock()
    profile = Profile(id=uuid4(), user_id=owner_id, display_name="Private User", lifestyle_vector=[0.0]*64, lifestyle_traits={})
    target_user = User(id=owner_id, email="priv@example.com", hashed_password="h", full_name="Private User")
    privacy = UserPrivacySetting(id=uuid4(), user_id=owner_id, profile_visibility="private")

    service = ProfileService(mock_db)
    service.get_by_user_id = AsyncMock(return_value=profile)
    service.get_privacy_settings = AsyncMock(return_value=privacy)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = mock_user_res

    with pytest.raises(ForbiddenException) as exc_info:
        await service.get_profile_with_privacy(requester_id=viewer_id, target_user_id=owner_id, is_admin=False)
    assert "private" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
async def test_privacy_strict_visibility_matched_only():
    """Matched-only profile raises ForbiddenException when users do not have an active mutual match."""
    owner_id = uuid4()
    viewer_id = uuid4()

    mock_db = AsyncMock()
    profile = Profile(id=uuid4(), user_id=owner_id, display_name="Matched Only User", lifestyle_vector=[0.0]*64, lifestyle_traits={})
    target_user = User(id=owner_id, email="matched@example.com", hashed_password="h", full_name="Matched User")
    privacy = UserPrivacySetting(id=uuid4(), user_id=owner_id, profile_visibility="matched_only")

    service = ProfileService(mock_db)
    service.get_by_user_id = AsyncMock(return_value=profile)
    service.get_privacy_settings = AsyncMock(return_value=privacy)

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = target_user
    mock_match_res = MagicMock()
    mock_match_res.scalar_one_or_none.return_value = None # Not mutually matched

    mock_db.execute.side_effect = [mock_user_res, mock_match_res]

    with pytest.raises(ForbiddenException) as exc_info:
        await service.get_profile_with_privacy(requester_id=viewer_id, target_user_id=owner_id, is_admin=False)
    assert "mutual matches" in str(exc_info.value.detail).lower()
