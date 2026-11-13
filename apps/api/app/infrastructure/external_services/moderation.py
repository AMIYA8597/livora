"""
Replaceable Content Moderation & Safety Provider Interface & Implementations.
Provides deterministic, zero-dependency heuristic moderation with optional ML enhancement and resilient fallback.
"""

from abc import ABC, abstractmethod
from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModerationCategory(str, Enum):
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    PHISHING_SCAM = "phishing_scam"
    PII_LEAK = "pii_leak"
    SPAM = "spam"
    SEXUAL = "sexual"
    VIOLENCE = "violence"


class ModerationResult(BaseModel):
    is_flagged: bool = False
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    categories: List[str] = Field(default_factory=list)
    flagged_terms: List[str] = Field(default_factory=list)
    action_recommended: str = "allow"  # allow, flag_for_review, block
    provider_used: str = "heuristic"


class BaseContentModerationProvider(ABC):
    """Abstract contract for content safety and moderation providers."""

    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        pass

    @abstractmethod
    async def check_content(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ModerationResult:
        pass


class HeuristicModerationProvider(BaseContentModerationProvider):
    """
    Default deterministic rule & pattern-based moderation provider.
    Zero external dependencies, instant execution, and zero cost.
    Detects scam patterns (UPI advance scams), PII leaks, harassment, and spam.
    """

    # Indian rental scam patterns
    SCAM_PATTERNS = [
        re.compile(r"(advance\s+(payment|token|money|rent)\s+before\s+visit)", re.IGNORECASE),
        re.compile(r"(transfer|send|gpay|paytm|phonepe)\s+(amount|money|token)\s+(first|now|advance)", re.IGNORECASE),
        re.compile(r"(western\s+union|gift\s+card|crypto|bitcoin)", re.IGNORECASE),
    ]

    # Indian phone number patterns (10 digits, +91, with spaces/dashes)
    PHONE_PATTERNS = [
        re.compile(r"(\+91[\-\s]?)?[6-9]\d{9}"),
        re.compile(r"\b[6-9]\d{4}\s*\d{5}\b"),
    ]

    # Abusive / harassment keywords
    ABUSIVE_KEYWORDS = {
        "abuse", "harass", "threat", "kill", "die", "bastard", "idiot", "fraud", "cheater",
        "scammer", "hate", "whore", "slut", "cunt", "motherfucker"
    }

    # Spam keywords
    SPAM_PATTERNS = [
        re.compile(r"(casino|lottery|poker|jackpot|free\s+crypto|make\s+money\s+fast)", re.IGNORECASE),
        re.compile(r"https?://[^\s]+"),  # External links
    ]

    def provider_name(self) -> str:
        return "heuristic_safety_filter"

    async def is_available(self) -> bool:
        return True

    async def check_content(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ModerationResult:
        context = context or {}
        text_lower = text.lower()
        flagged_categories: List[str] = []
        flagged_terms: List[str] = []
        risk_score = 0.0

        # 1. Scam detection
        for pat in self.SCAM_PATTERNS:
            match = pat.search(text)
            if match:
                flagged_categories.append(ModerationCategory.PHISHING_SCAM.value)
                flagged_terms.append(match.group(0))
                risk_score = max(risk_score, 0.85)

        # 2. Harassment & abusive terms
        words = set(re.findall(r"\b\w+\b", text_lower))
        found_abusive = words.intersection(self.ABUSIVE_KEYWORDS)
        if found_abusive:
            flagged_categories.append(ModerationCategory.HARASSMENT.value)
            flagged_terms.extend(list(found_abusive))
            risk_score = max(risk_score, 0.90)

        # 3. PII leak (phone numbers in early unverified conversations)
        if context.get("check_pii", False):
            for pat in self.PHONE_PATTERNS:
                match = pat.search(text)
                if match:
                    flagged_categories.append(ModerationCategory.PII_LEAK.value)
                    flagged_terms.append(match.group(0))
                    risk_score = max(risk_score, 0.60)

        # 4. Spam detection
        for pat in self.SPAM_PATTERNS:
            match = pat.search(text)
            if match:
                flagged_categories.append(ModerationCategory.SPAM.value)
                flagged_terms.append(match.group(0))
                risk_score = max(risk_score, 0.70)

        is_flagged = len(flagged_categories) > 0
        action = "allow"
        if is_flagged:
            if risk_score >= 0.80:
                action = "block"
            else:
                action = "flag_for_review"

        return ModerationResult(
            is_flagged=is_flagged,
            risk_score=risk_score,
            categories=list(set(flagged_categories)),
            flagged_terms=flagged_terms,
            action_recommended=action,
            provider_used=self.provider_name(),
        )


class MockExternalMLModerationProvider(BaseContentModerationProvider):
    """
    Optional external LLM or AI content moderation API (e.g. OpenAI/Perspective).
    """

    def __init__(self, api_key: Optional[str] = None, enabled: bool = False):
        self.api_key = api_key
        self.enabled = enabled

    def provider_name(self) -> str:
        return "external_ml_moderation_service"

    async def is_available(self) -> bool:
        return self.enabled and bool(self.api_key)

    async def check_content(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ModerationResult:
        if not await self.is_available():
            raise RuntimeError("External AI moderation API key missing or provider disabled")

        # Simulated ML sentiment/toxicity scoring
        return ModerationResult(
            is_flagged=False,
            risk_score=0.05,
            categories=[],
            flagged_terms=[],
            action_recommended="allow",
            provider_used=self.provider_name(),
        )


class ResilientModerationService:
    """
    Composite safety service: delegates to primary ML provider when configured,
    and seamlessly falls back to Heuristic provider on error or absence.
    """

    def __init__(
        self,
        primary_provider: Optional[BaseContentModerationProvider] = None,
        fallback_provider: Optional[BaseContentModerationProvider] = None,
    ):
        self.fallback = fallback_provider or HeuristicModerationProvider()
        self.primary = primary_provider or self.fallback

    async def moderate(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ModerationResult:
        if self.primary != self.fallback:
            try:
                if await self.primary.is_available():
                    return await self.primary.check_content(text, context=context)
            except Exception as exc:
                logger.warning(
                    f"Primary moderation provider [{self.primary.provider_name()}] failed: {exc}. "
                    "Falling back to heuristic moderation."
                )

        return await self.fallback.check_content(text, context=context)
