"""
Unit and Integration Tests for 10-Dimension Explainable Compatibility Engine,
Dealbreakers, and Mutual Match Lifecycle.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.matching.engine import (
    DIMENSION_WEIGHTS,
    compute_10_dimension_compatibility,
    ALGORITHM_VERSION,
)
from app.modules.matching.service import MatchingService
from tests.matching_mocks import interactions_found
from app.modules.matching.models import MatchInteraction
from app.core.exceptions import BadRequestException

def test_10_dimension_weights_sum_to_one():
    """Verify all 10 dimension weights sum exactly to 1.0 (100%)."""
    total_weight = sum(DIMENSION_WEIGHTS.values())
    assert abs(total_weight - 1.0) < 0.0001
    assert len(DIMENSION_WEIGHTS) == 10
    assert DIMENSION_WEIGHTS["working_schedule"] == 0.15
    assert DIMENSION_WEIGHTS["sleep_schedule"] == 0.15
    assert DIMENSION_WEIGHTS["budget"] == 0.15
    assert DIMENSION_WEIGHTS["cleanliness"] == 0.12
    assert DIMENSION_WEIGHTS["lifestyle"] == 0.12
    assert DIMENSION_WEIGHTS["noise_and_lighting"] == 0.10
    assert DIMENSION_WEIGHTS["guests_and_social"] == 0.07
    assert DIMENSION_WEIGHTS["food_and_cooking"] == 0.05
    assert DIMENSION_WEIGHTS["professional_domain"] == 0.05
    assert DIMENSION_WEIGHTS["location"] == 0.04

def test_10_dimension_factor_explanations_and_scoring():
    """Verify each dimension computes factor-level scores and explainable text."""
    user_traits = {
        "work_arrangement": "hybrid",
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "chore_philosophy": "shared_roster",
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
        "diet_preference": "pure_veg",
        "non_veg_cooking_allowed": False,
        "cooks_at_home": "sometimes",
        "smoking": "never",
        "drinking": "socially",
        "pet_preference": "cats_and_dogs_ok",
    }
    target_traits = {
        "work_arrangement": "hybrid",
        "sleep_schedule": "early_bird",
        "cleanliness_level": 4,
        "chore_philosophy": "shared_roster",
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
        "diet_preference": "pure_veg",
        "non_veg_cooking_allowed": False,
        "cooks_at_home": "sometimes",
        "smoking": "never",
        "drinking": "socially",
        "pet_preference": "cats_and_dogs_ok",
    }

    res = compute_10_dimension_compatibility(
        user_traits=user_traits,
        target_traits=target_traits,
        user_budget=(20000, 30000),
        target_budget=(22000, 32000),
        user_occupation="Software Engineer",
        target_occupation="Backend Engineer",
        user_domain="Technology",
        target_domain="Technology",
        user_preferred_locs=["Indiranagar"],
        target_preferred_locs=["Indiranagar"],
        vector_sim=0.95,
    )

    assert res["overall_score"] >= 90.0
    assert res["dealbreakers_cleared"] is True
    assert len(res["conflicts"]) == 0
    assert res["algorithm_version"] == ALGORITHM_VERSION
    assert len(res["factors"]) == 10
    assert len(res["explanations"]) == 10
    assert "Indiranagar" in res["explanations"]["location"]

def test_dealbreaker_enforcement_caps_score():
    """Verify violated dealbreaker zeroes out or caps score at 30 with explicit conflict reason."""
    user_traits = {
        "smoking": "never",
        "diet_preference": "pure_veg",
        "non_veg_cooking_allowed": False,
        "cleanliness_level": 5,
    }
    # Candidate smokes permitted inside and cooks non-veg in pure veg kitchen
    target_traits = {
        "smoking": "permitted",
        "diet_preference": "non_veg",
        "cleanliness_level": 5,
    }

    res = compute_10_dimension_compatibility(
        user_traits=user_traits,
        target_traits=target_traits,
        user_budget=(15000, 25000),
        target_budget=(15000, 25000),
    )

    assert res["dealbreakers_cleared"] is False
    assert res["overall_score"] <= 30.0
    assert len(res["conflicts"]) >= 1
    assert any("smoking" in c.lower() for c in res["conflicts"])

@pytest.mark.asyncio
async def test_mutual_match_lifecycle_transactional():
    """Verify reciprocal like generates MutualMatch with canonical pair ordering."""
    user_a = uuid4()
    user_b = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = MatchingService(mock_db)
    service._pair_scores = AsyncMock(return_value=None)  # profile reads not mocked here

    # 1. User A likes User B (Initial interaction, target hasn't liked back yet)

    mock_no_block = MagicMock()
    mock_no_block.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [mock_no_block, interactions_found()]  # neither has decided yet

    res_a = await service.record_interaction(user_a, user_b, action="like")
    assert res_a.is_mutual_match is False
    assert res_a.mutual_match_id is None

    # 2. Rejection of self-interaction
    with pytest.raises(BadRequestException) as exc_info:
        await service.record_interaction(user_a, user_a, action="like")
    assert "cannot record an interaction with yourself" in str(exc_info.value.detail).lower()

    # 3. User B likes User A back (Reciprocal like found -> Mutual Match created!)

    reciprocal_match_from_a = MatchInteraction(user_id=user_a, target_user_id=user_b, action="like")

    mock_existing_mutual = MagicMock()
    mock_existing_mutual.scalar_one_or_none.return_value = None

    # Mock pairwise score call inside record_interaction
    service.get_pairwise_score = AsyncMock()
    mock_breakdown = MagicMock()
    mock_breakdown.overall_score = 88.5
    mock_breakdown.model_dump.return_value = {"overall_score": 88.5}
    service.get_pairwise_score.return_value = mock_breakdown

    mock_db.execute.side_effect = [mock_no_block, interactions_found(reciprocal_match_from_a), mock_existing_mutual]

    res_b = await service.record_interaction(user_b, user_a, action="like")
    assert res_b.is_mutual_match is True
    assert res_b.compatibility_score == 88.5
    assert mock_db.commit.called
