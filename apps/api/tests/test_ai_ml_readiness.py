import pytest
from uuid import uuid4

from app.infrastructure.external_services.recommendations import (
    DeterministicRecommendationProvider,
    MockExternalMLRecommendationProvider,
    ResilientRecommendationService,
)
from app.infrastructure.external_services.moderation import (
    HeuristicModerationProvider,
    MockExternalMLModerationProvider,
    ModerationCategory,
    ResilientModerationService,
)
from app.infrastructure.external_services.semantic_search import (
    FaultTolerantSearchService,
    KeywordFallbackSearchProvider,
    PgvectorSemanticSearchProvider,
)


@pytest.mark.asyncio
async def test_deterministic_recommendation_provider():
    provider = DeterministicRecommendationProvider()
    assert provider.provider_name() == "deterministic_10d_engine"
    assert await provider.is_available() is True

    target_user_id = uuid4()
    candidate_1_id = uuid4()
    candidate_2_id = uuid4()

    target_profile = {
        "user_id": target_user_id,
        "sleep_schedule": "early_bird",
        "work_schedule": "fixed_day",
        "cleanliness_level": "very_clean",
        "diet_preference": "vegetarian",
        "smoking_policy": "never",
        "budget_min": 10000,
        "budget_max": 20000,
    }

    # High match candidate
    cand_high = {
        "user_id": candidate_1_id,
        "sleep_schedule": "early_bird",
        "work_schedule": "fixed_day",
        "cleanliness_level": "very_clean",
        "diet_preference": "vegetarian",
        "smoking_policy": "never",
        "budget_min": 12000,
        "budget_max": 18000,
    }

    # Low match candidate (conflicting schedule & diet & smoking)
    cand_low = {
        "user_id": candidate_2_id,
        "sleep_schedule": "night_owl",
        "work_schedule": "rotational",
        "cleanliness_level": "relaxed",
        "diet_preference": "non_vegetarian",
        "smoking_policy": "regular",
        "budget_min": 35000,
        "budget_max": 50000,
    }

    ranked = await provider.rank_candidates(target_profile, [cand_low, cand_high])
    assert len(ranked) == 2
    # cand_high should be ranked #1
    assert ranked[0].user_id == candidate_1_id
    assert ranked[0].rank == 1
    assert ranked[0].score > ranked[1].score
    assert ranked[1].user_id == candidate_2_id
    assert ranked[1].rank == 2
    assert "cleanliness" in ranked[0].dimension_breakdown


@pytest.mark.asyncio
async def test_ml_recommendation_resilient_fallback():
    # 1. Configured & available ML provider
    ml_provider = MockExternalMLRecommendationProvider(
        endpoint_url="https://api.internal.ai/v1/rerank",
        api_key="sk-test-key",
        enabled=True,
    )
    assert await ml_provider.is_available() is True

    service = ResilientRecommendationService(primary_provider=ml_provider)
    cand_id = uuid4()
    res = await service.get_ranked_candidates({"user_id": uuid4()}, [{"user_id": cand_id}])
    assert len(res) == 1
    assert res[0].provider_used == "external_ml_reranker"

    # 2. ML provider raises error -> falls back to deterministic without crashing
    class BrokenMLProvider(MockExternalMLRecommendationProvider):
        async def rank_candidates(self, target_profile, candidates, limit=20):
            raise ConnectionError("ML Model endpoint unreachable or timed out")

    broken_service = ResilientRecommendationService(
        primary_provider=BrokenMLProvider(endpoint_url="http://fail", api_key="k", enabled=True)
    )

    fallback_res = await broken_service.get_ranked_candidates(
        {"user_id": uuid4(), "sleep_schedule": "early_bird", "budget_min": 10000, "budget_max": 20000},
        [{"user_id": cand_id, "sleep_schedule": "early_bird", "budget_min": 10000, "budget_max": 20000}],
    )
    assert len(fallback_res) == 1
    assert fallback_res[0].provider_used == "deterministic_10d_engine"


@pytest.mark.asyncio
async def test_heuristic_moderation_scam_detection():
    provider = HeuristicModerationProvider()
    assert await provider.is_available() is True

    # Scam message
    scam_text = "Please transfer money advance before visit to reserve the flat immediately"
    res = await provider.check_content(scam_text)
    assert res.is_flagged is True
    assert ModerationCategory.PHISHING_SCAM.value in res.categories
    assert res.action_recommended == "block"

    # Safe message
    safe_text = "Hi! I am interested in viewing the 2BHK flat this Saturday afternoon."
    safe_res = await provider.check_content(safe_text)
    assert safe_res.is_flagged is False
    assert safe_res.action_recommended == "allow"


@pytest.mark.asyncio
async def test_heuristic_moderation_harassment_and_pii():
    provider = HeuristicModerationProvider()

    harass_text = "You are a complete idiot and fraud, I will harass you"
    res = await provider.check_content(harass_text)
    assert res.is_flagged is True
    assert ModerationCategory.HARASSMENT.value in res.categories

    # Phone leak detection when check_pii context is passed
    pii_text = "Call me directly on +91 9876543210 for offline booking"
    pii_res = await provider.check_content(pii_text, context={"check_pii": True})
    assert pii_res.is_flagged is True
    assert ModerationCategory.PII_LEAK.value in pii_res.categories


@pytest.mark.asyncio
async def test_moderation_resilient_fallback():
    class FailingAIModeration(MockExternalMLModerationProvider):
        async def check_content(self, text, context=None):
            raise TimeoutError("External moderation API timed out after 3000ms")

    service = ResilientModerationService(
        primary_provider=FailingAIModeration(api_key="test", enabled=True)
    )

    # Should not throw exception, must fall back to heuristic
    result = await service.moderate("Advance payment before visit is mandatory")
    assert result.is_flagged is True
    assert ModerationCategory.PHISHING_SCAM.value in result.categories
    assert result.provider_used == "heuristic_safety_filter"


@pytest.mark.asyncio
async def test_semantic_and_keyword_search_providers():
    pg_provider = PgvectorSemanticSearchProvider(embedding_dimension=64)
    items = [
        {
            "id": uuid4(),
            "title": "Spacious 2BHK in Koramangala near Sony Signal",
            "description": "Quiet flat with high speed wifi, suitable for working professionals and techies",
            "locality": "Koramangala",
        },
        {
            "id": uuid4(),
            "title": "1RK Studio Apartment in HSR Layout",
            "description": "Compact studio for students near coaching institutes",
            "locality": "HSR Layout",
        },
    ]

    # Test pgvector similarity
    pg_results = await pg_provider.search("Koramangala techie flat", items)
    assert len(pg_results) == 2
    assert "Koramangala" in pg_results[0].title

    # Test keyword fallback
    kw_provider = KeywordFallbackSearchProvider()
    kw_results = await kw_provider.search("HSR Layout studio", items)
    assert len(kw_results) >= 1
    assert "HSR Layout" in kw_results[0].title

    # Test fault-tolerant composite
    class BrokenVectorSearch(PgvectorSemanticSearchProvider):
        async def search(self, query, items, limit=10):
            raise RuntimeError("Postgres extension vector not found in DB")

    tolerant_service = FaultTolerantSearchService(
        primary_provider=BrokenVectorSearch(),
        fallback_provider=kw_provider,
    )

    results = await tolerant_service.search("Koramangala 2BHK", items)
    assert len(results) >= 1
    assert results[0].provider_used == "token_keyword_search"
