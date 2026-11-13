"""
External Services & Provider Adapters.
Defines replaceable interfaces and zero-dependency fallbacks for:
- Recommendations (Deterministic 10-dimension compatibility engine + optional ML)
- Safety & Moderation (Heuristic regex/keyword filter + optional external LLM/Perspective)
- Semantic Search (Pgvector dense vector similarity + token keyword fallback)
"""

from app.infrastructure.external_services.recommendations import (
    BaseRecommendationProvider,
    CandidateRankItem,
    DeterministicRecommendationProvider,
    MockExternalMLRecommendationProvider,
    ResilientRecommendationService,
)
from app.infrastructure.external_services.moderation import (
    BaseContentModerationProvider,
    HeuristicModerationProvider,
    MockExternalMLModerationProvider,
    ModerationCategory,
    ModerationResult,
    ResilientModerationService,
)
from app.infrastructure.external_services.semantic_search import (
    BaseSemanticSearchProvider,
    FaultTolerantSearchService,
    KeywordFallbackSearchProvider,
    PgvectorSemanticSearchProvider,
    SemanticSearchResultItem,
)

__all__ = [
    "BaseRecommendationProvider",
    "CandidateRankItem",
    "DeterministicRecommendationProvider",
    "MockExternalMLRecommendationProvider",
    "ResilientRecommendationService",
    "BaseContentModerationProvider",
    "HeuristicModerationProvider",
    "MockExternalMLModerationProvider",
    "ModerationCategory",
    "ModerationResult",
    "ResilientModerationService",
    "BaseSemanticSearchProvider",
    "FaultTolerantSearchService",
    "KeywordFallbackSearchProvider",
    "PgvectorSemanticSearchProvider",
    "SemanticSearchResultItem",
]
