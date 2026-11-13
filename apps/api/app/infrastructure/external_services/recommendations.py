"""
Replaceable Recommendation Provider Interface & Implementations.
Provides deterministic baseline matching with graceful ML augmentation and zero-crash fallback.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.modules.matching.engine import compute_10_dimension_compatibility

logger = logging.getLogger(__name__)


class CandidateRankItem(BaseModel):
    user_id: UUID
    score: float = Field(ge=0.0, le=100.0)
    rank: int = Field(ge=1)
    match_reason: str
    dimension_breakdown: Dict[str, float] = Field(default_factory=dict)
    provider_used: str = "deterministic"


class BaseRecommendationProvider(ABC):
    """Abstract contract for recommendation ranking providers."""

    @abstractmethod
    def provider_name(self) -> str:
        """Returns the unique identifier for the provider."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Returns True if the provider is healthy and configured."""
        pass

    @abstractmethod
    async def rank_candidates(
        self,
        target_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 20,
    ) -> List[CandidateRankItem]:
        """Rank a list of candidates against the target user profile."""
        pass


class DeterministicRecommendationProvider(BaseRecommendationProvider):
    """
    Default production provider: evaluates candidates using the explainable
    10-dimension compatibility engine. Guaranteed deterministic, reproducible,
    and requires no external network or paid ML dependencies.
    """

    def provider_name(self) -> str:
        return "deterministic_10d_engine"

    async def is_available(self) -> bool:
        return True

    async def rank_candidates(
        self,
        target_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 20,
    ) -> List[CandidateRankItem]:
        results: List[CandidateRankItem] = []

        user_budget = (
            int(target_profile.get("budget_min", 10000)),
            int(target_profile.get("budget_max", 30000)),
        )

        for candidate in candidates:
            cand_id = candidate.get("user_id")
            if not cand_id:
                continue

            try:
                cand_budget = (
                    int(candidate.get("budget_min", 10000)),
                    int(candidate.get("budget_max", 30000)),
                )

                comp_result = compute_10_dimension_compatibility(
                    user_traits=target_profile,
                    target_traits=candidate,
                    user_budget=user_budget,
                    target_budget=cand_budget,
                    user_dealbreakers=target_profile.get("dealbreakers", []),
                )

                score = float(comp_result.get("overall_score", 50.0))
                factors = comp_result.get("factors", {})
                cleared = comp_result.get("dealbreakers_cleared", True)
                conflicts = comp_result.get("conflicts", [])

                reason = "High overall lifestyle and schedule alignment"
                if not cleared and conflicts:
                    reason = f"Dealbreaker conflict: {'; '.join(conflicts[:2])}"

                results.append(
                    CandidateRankItem(
                        user_id=cand_id if isinstance(cand_id, UUID) else UUID(str(cand_id)),
                        score=score,
                        rank=1,
                        match_reason=reason,
                        dimension_breakdown={k: float(v) for k, v in factors.items()},
                        provider_used=self.provider_name(),
                    )
                )
            except Exception as e:
                logger.warning(f"Error calculating score for candidate {cand_id}: {e}")
                continue

        # Sort descending by score
        results.sort(key=lambda item: item.score, reverse=True)
        for idx, item in enumerate(results[:limit]):
            item.rank = idx + 1

        return results[:limit]


class MockExternalMLRecommendationProvider(BaseRecommendationProvider):
    """
    Optional external ML / vector reranking provider.
    Can be configured with an API endpoint or local embedding model.
    """

    def __init__(self, endpoint_url: Optional[str] = None, api_key: Optional[str] = None, enabled: bool = False):
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.enabled = enabled

    def provider_name(self) -> str:
        return "external_ml_reranker"

    async def is_available(self) -> bool:
        return self.enabled and bool(self.endpoint_url or self.api_key)

    async def rank_candidates(
        self,
        target_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 20,
    ) -> List[CandidateRankItem]:
        if not await self.is_available():
            raise RuntimeError("ML recommendation provider is offline or not configured")

        # Simulated ML neural reranking
        ranked: List[CandidateRankItem] = []
        for idx, c in enumerate(candidates[:limit]):
            cand_id = c.get("user_id")
            ranked.append(
                CandidateRankItem(
                    user_id=cand_id if isinstance(cand_id, UUID) else UUID(str(cand_id)),
                    score=round(95.0 - (idx * 2.5), 2),
                    rank=idx + 1,
                    match_reason="ML collaborative vector affinity match",
                    dimension_breakdown={"neural_vector_similarity": 0.92},
                    provider_used=self.provider_name(),
                )
            )
        return ranked


class ResilientRecommendationService:
    """
    Composite service that orchestrates primary and fallback providers.
    Never crashes: if an optional ML provider fails or is disabled, gracefully
    falls back to the Deterministic 10-dimension provider.
    """

    def __init__(
        self,
        primary_provider: Optional[BaseRecommendationProvider] = None,
        fallback_provider: Optional[BaseRecommendationProvider] = None,
    ):
        self.fallback = fallback_provider or DeterministicRecommendationProvider()
        self.primary = primary_provider or self.fallback

    async def get_ranked_candidates(
        self,
        target_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        limit: int = 20,
    ) -> List[CandidateRankItem]:
        if self.primary != self.fallback:
            try:
                if await self.primary.is_available():
                    return await self.primary.rank_candidates(target_profile, candidates, limit=limit)
            except Exception as exc:
                logger.warning(
                    f"Primary recommendation provider [{self.primary.provider_name()}] failed: {exc}. "
                    "Falling back to deterministic engine."
                )

        # Fallback guaranteed
        return await self.fallback.rank_candidates(target_profile, candidates, limit=limit)
