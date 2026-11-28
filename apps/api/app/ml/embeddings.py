"""
Text embeddings for listing and "about me" search.

Two providers share one interface:

- `VoyageEmbedder`: Voyage AI embeddings (Anthropic's recommended embeddings provider). Real
  semantic similarity: "quiet place near my office in Koramangala" matches a listing that says
  "calm 2BHK, 5 minutes from Forum Mall" with no words in common.
- `LocalHashingEmbedder`: deterministic hashed word and character n-grams. No network, no cost,
  typo-tolerant ("koramangla" still matches), but lexical: it only matches shared words and
  word pieces. It is the default so the product works without an API key.

Every vector is stored with `provider.model_id`, and search only compares vectors with the same
model id, so switching providers can never mix incompatible vector spaces.
"""
from __future__ import annotations
from app.modules.lifestyle.traits import canonical_traits

import hashlib
import logging
import math
import re
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Dict, List, Literal, Optional, Protocol, Sequence, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger("flatmate.ml.embeddings")

EMBEDDING_DIM = 512  # matches content_embeddings.embedding_vec vector(512) (migration 009)
MAX_TEXT_CHARS = 4000

Kind = Literal["document", "query"]


class EmbeddingUnavailable(RuntimeError):
    """The provider could not produce embeddings (network, quota, bad response)."""


class Embedder(Protocol):
    model_id: str
    dimensions: int
    # Cosine similarity below which a document is not considered relevant to a query.
    min_similarity: float
    # If set, a document must also be within this much of the best match's similarity.
    relative_margin: Optional[float]

    async def embed(self, texts: Sequence[str], kind: Kind) -> List[List[float]]: ...


_TOKEN = re.compile(r"[a-z0-9]+")


def _stable_hash(feature: str) -> int:
    # blake2b, not hash(): Python's string hash is salted per process.
    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


def normalize(vec: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else list(vec)


class LocalHashingEmbedder:
    """Feature hashing of words, word bigrams and character 3/4-grams, with sublinear counts.

    Signed hashing (a second hash bit picks +1/-1) keeps collisions from piling up in one
    direction, so cosine similarity stays close to the true n-gram overlap.
    """

    # Chosen by simulation over judged query/listing pairs with random noise text: at 0.15 a
    # wrong listing passes for ~0.1% of queries while typos ("koramangla", "indranagar") always
    # match. Paraphrases with no shared word pieces ("food" vs "meals") need a real model.
    min_similarity = 0.15
    relative_margin: Optional[float] = None

    def __init__(self, dimensions: int = EMBEDDING_DIM):
        self.dimensions = dimensions
        self.model_id = f"local-hash-v2-{dimensions}"

    def _features(self, text: str) -> dict[str, float]:
        words = _TOKEN.findall(text.lower()[:MAX_TEXT_CHARS])
        counts: dict[str, float] = {}

        def add(feature: str, weight: float) -> None:
            counts[feature] = counts.get(feature, 0.0) + weight

        for i, w in enumerate(words):
            add(f"w:{w}", 1.0)
            if i + 1 < len(words):
                add(f"b:{w}_{words[i + 1]}", 0.5)
            padded = f"<{w}>"
            for n in (3, 4):
                for j in range(len(padded) - n + 1):
                    add(f"c{n}:{padded[j:j + n]}", 1.0)
        return counts

    def embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dimensions
        for feature, count in self._features(text).items():
            h = _stable_hash(feature)
            sign = 1.0 if (h >> 63) & 1 else -1.0
            vec[h % self.dimensions] += sign * (1.0 + math.log(count)) if count >= 1 else sign * count
        return normalize(vec)

    async def embed(self, texts: Sequence[str], kind: Kind) -> List[List[float]]:
        return [self.embed_one(t) for t in texts]


class VoyageEmbedder:
    """Voyage AI embeddings over HTTPS. Batches requests and fails fast (EmbeddingUnavailable).

    Rate limits are tight on small accounts (3 requests a minute without a payment method), so:
    query vectors are cached in memory (popular searches cost one request), and after a 429 the
    embedder stops calling Voyage until the window has passed, so searches go straight to the
    keyword path instead of each waiting on a request that will be refused.
    """

    URL = "https://api.voyageai.com/v1/embeddings"
    BATCH = 128
    QUERY_CACHE_SIZE = 1024
    DEFAULT_COOLDOWN_SECONDS = 60.0
    # Neural similarities sit in a narrow band that depends on the corpus (listings that share
    # boilerplate all score close together), so a fixed cut-off either keeps everything or
    # nothing. Keep what scores close to the best match, above a low absolute floor.
    min_similarity = 0.2
    relative_margin: Optional[float] = 0.06

    def __init__(self, api_key: str, model: str, dimensions: int = EMBEDDING_DIM, timeout: float = 8.0):
        self._api_key = api_key
        self._model = model
        self.dimensions = dimensions
        self.model_id = f"voyage:{model}:{dimensions}"
        self._timeout = timeout
        self._query_cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._blocked_until = 0.0

    @staticmethod
    def _cache_key(text: str) -> str:
        return " ".join(text.lower().split())

    def _retry_after(self, res: httpx.Response) -> float:
        try:
            return max(1.0, min(float(res.headers.get("retry-after", "")), 600.0))
        except ValueError:
            return self.DEFAULT_COOLDOWN_SECONDS

    async def embed(self, texts: Sequence[str], kind: Kind) -> List[List[float]]:
        cached: Dict[int, List[float]] = {}
        if kind == "query":
            for i, t in enumerate(texts):
                hit = self._query_cache.get(self._cache_key(t))
                if hit is not None:
                    self._query_cache.move_to_end(self._cache_key(t))
                    cached[i] = hit
        todo: List[Tuple[int, str]] = [(i, t) for i, t in enumerate(texts) if i not in cached]
        if todo and time.monotonic() < self._blocked_until:
            raise EmbeddingUnavailable("Voyage embeddings failed: rate limited (cooling down)")

        fresh: Dict[int, List[float]] = {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(todo), self.BATCH):
                chunk = todo[start:start + self.BATCH]
                batch = [t[:MAX_TEXT_CHARS] or " " for _, t in chunk]
                try:
                    res = await client.post(
                        self.URL,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json={
                            "input": batch,
                            "model": self._model,
                            "input_type": kind,
                            "output_dimension": self.dimensions,
                        },
                    )
                    if res.status_code == 429:
                        self._blocked_until = time.monotonic() + self._retry_after(res)
                    res.raise_for_status()
                    data = sorted(res.json()["data"], key=lambda d: d["index"])
                except httpx.HTTPStatusError as exc:
                    raise EmbeddingUnavailable(
                        f"Voyage embeddings failed: HTTP {exc.response.status_code}") from exc
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    raise EmbeddingUnavailable(f"Voyage embeddings failed: {type(exc).__name__}") from exc
                if len(data) != len(batch) or any(len(d["embedding"]) != self.dimensions for d in data):
                    raise EmbeddingUnavailable("Voyage returned an unexpected number or size of vectors")
                for (i, t), d in zip(chunk, data):
                    fresh[i] = normalize(d["embedding"])
                    if kind == "query":
                        self._query_cache[self._cache_key(t)] = fresh[i]
                        if len(self._query_cache) > self.QUERY_CACHE_SIZE:
                            self._query_cache.popitem(last=False)
        return [cached[i] if i in cached else fresh[i] for i in range(len(texts))]


@lru_cache(maxsize=4)
def get_embedder(entity_type: str = "property") -> Embedder:
    """The embedder for listings (and listing searches), or for people's profiles.

    Profiles hold personal "about me" text, so they stay on the in-process embedder unless
    EXTERNAL_PROFILE_EMBEDDINGS is on: an outside provider may keep what it is sent (Voyage does,
    for training, unless the account has opted out). Vectors are tagged with their model, so the
    two kinds never get compared with each other.
    """
    if entity_type == "profile" and not settings.EXTERNAL_PROFILE_EMBEDDINGS:
        return LocalHashingEmbedder()
    provider = (settings.EMBEDDING_PROVIDER or "local").lower()
    if provider == "voyage":
        if settings.VOYAGE_API_KEY:
            return VoyageEmbedder(
                settings.VOYAGE_API_KEY, settings.EMBEDDING_MODEL,
                timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
            )
        logger.warning("EMBEDDING_PROVIDER=voyage but VOYAGE_API_KEY is not set: using local embeddings")
    return LocalHashingEmbedder()


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1]; 0 when either vector is empty or zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------------------------------------
# What gets embedded. Names, phone numbers, exact addresses and emails are never included.
# ---------------------------------------------------------------------------------------------

_TRAIT_WORDS = {
    "sleep_schedule": {"early_bird": "early riser", "night_owl": "night owl, stays up late",
                       "flexible": "flexible sleep schedule", "rotational": "rotational shifts"},
    "smoking": {"never": "non-smoker", "outside_only": "smokes outside only", "permitted": "smoker"},
    "drinking": {"teetotaler": "doesn't drink", "socially": "drinks socially", "regular": "drinks regularly"},
    "diet_preference": {"pure_veg": "pure vegetarian", "jain": "jain vegetarian",
                        "eggetarian": "eggetarian", "non_veg": "eats non-veg", "vegan": "vegan"},
    "cooks_at_home": {"daily": "cooks daily", "hires_cook": "has a cook", "orders_online": "orders food in"},
    "pet_preference": {"loves_pets": "loves pets", "cats_and_dogs_ok": "fine with cats and dogs",
                       "cats_ok": "fine with cats", "dogs_ok": "fine with dogs", "no_pets": "no pets",
                       "allergic": "allergic to pets"},
    "noise_tolerance": {"quiet_library": "likes a quiet home", "lively": "likes a lively home"},
    "guests_policy": {"rarely": "rarely has guests", "open_house": "often has guests over"},
    "work_arrangement": {"remote": "works from home", "hybrid": "hybrid work",
                         "on_site": "works at the office", "shift_work": "shift work"},
    "social_battery": {"introverted": "introvert, quiet", "moderate": "moderately social",
                       "extroverted": "extrovert, social", "balanced": "balanced social life"},
}


def profile_text(profile) -> str:
    parts: List[str] = []
    if profile.bio:
        parts.append(profile.bio)
    if profile.occupation:
        parts.append(f"Works as {profile.occupation}.")
    traits = canonical_traits(profile.lifestyle_traits)
    for key, words in _TRAIT_WORDS.items():
        value = traits.get(key)
        if isinstance(value, str) and value in words:
            parts.append(words[value])
    if profile.preferred_locations:
        parts.append("Looking in " + ", ".join(profile.preferred_locations[:8]))
    return ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip())


def property_text(prop, amenity_keys: Sequence[str] = ()) -> str:
    furnishing = (prop.furnishing_status or "").replace("_", " ")
    parts = [
        prop.title,
        f"{prop.configuration} {(prop.property_category or '').replace('_', ' ')}",
        furnishing,
        f"in {prop.address_display}, {prop.city}",
        "pets allowed" if prop.pets_allowed else "",
        "smoking allowed" if prop.smoking_allowed else "",
        ", ".join(a.replace("_", " ") for a in amenity_keys),
        prop.description,
    ]
    return ". ".join(p.strip() for p in parts if p and p.strip())


def content_hash(model_id: str, text: str) -> str:
    return hashlib.sha256(f"{model_id}\n{text}".encode("utf-8")).hexdigest()
