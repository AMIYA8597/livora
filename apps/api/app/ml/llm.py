"""
Claude client for small structured tasks (moderation verdicts, reply suggestions).

- Uses structured outputs (`output_config.format` with a JSON schema), so responses always parse.
- Low effort: these are short classification/generation tasks on a latency budget.
- Opts into server-side refusal fallbacks on models that support them.
- Fails closed to the caller: every problem becomes `LLMUnavailable`, and each feature has a
  non-LLM path, so an outage or a missing key never breaks a user request.

Privacy: callers send only the text being judged plus minimal context (no names, emails,
phone numbers or account ids). Disable with AI_MODERATION_ENABLED / AI_SMART_REPLIES_ENABLED,
or by leaving ANTHROPIC_API_KEY unset.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

import anthropic

from app.core.config import settings

logger = logging.getLogger("flatmate.ml.llm")

# Models that accept `fallbacks: "default"` (beta server-side-fallback-2026-07-01).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(RuntimeError):
    """No usable answer: not configured, network/API error, refusal, or truncated output."""


def llm_configured() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


@lru_cache(maxsize=1)
def _client() -> Optional[anthropic.AsyncAnthropic]:
    if not settings.ANTHROPIC_API_KEY:
        return None
    return anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=1,
    )


async def structured_call(
    system: str,
    user: str,
    schema: Dict[str, Any],
    *,
    max_tokens: int = 2048,
    effort: str = "low",
) -> Dict[str, Any]:
    client = _client()
    if client is None:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")

    model = settings.LLM_MODEL
    params: Dict[str, Any] = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    try:
        if model in _FALLBACK_MODELS:
            response = await client.beta.messages.create(betas=[_FALLBACK_BETA], fallbacks="default", **params)
        else:
            response = await client.messages.create(**params)
    except anthropic.RateLimitError as exc:
        raise LLMUnavailable("Claude rate limit reached") from exc
    except anthropic.APIStatusError as exc:
        logger.warning("Claude API error %s (request %s)", exc.status_code, getattr(exc, "request_id", None))
        raise LLMUnavailable(f"Claude API error {exc.status_code}") from exc
    except anthropic.APIConnectionError as exc:  # includes timeouts
        raise LLMUnavailable("Could not reach the Claude API") from exc

    if response.stop_reason == "refusal":
        raise LLMUnavailable("Claude declined the request")
    if response.stop_reason == "max_tokens":
        raise LLMUnavailable("Claude's answer was cut off")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise LLMUnavailable("Claude returned no text")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LLMUnavailable("Claude returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("Claude returned an unexpected shape")
    return data
