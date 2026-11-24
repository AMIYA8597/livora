"""
The one shape lifestyle answers take wherever they are compared.

People answer the 10-dimension lifestyle form (`lifestyle_profiles`, PUT /lifestyle/me). Matching,
the flatmate filters, the ranker, embeddings and smart replies read the copy on the profile,
`profiles.lifestyle_traits`. Every save of the form rewrites that copy (and the matching vector)
from the answers, using the form's own keys and values: `diet_preference` (pure_veg, jain,
eggetarian, non_veg, vegan), `pet_preference`, `smoking` (never, outside_only, permitted), ...

The older quiz (POST /profiles/me/quiz) used other keys and values (`diet: vegetarian`,
`pets: has_cat`, `smoking: allowed`); `canonical_traits` converts them, and migration 015
converted the rows already stored.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

# Form fields copied to the profile, in the order of the form's dimensions.
TRAIT_FIELDS = (
    "sleep_schedule",
    "work_arrangement",
    "cleanliness_level",
    "chore_philosophy",
    "noise_tolerance",
    "instrument_or_music",
    "lighting_preference",
    "guests_policy",
    "social_battery",
    "diet_preference",
    "non_veg_cooking_allowed",
    "cooks_at_home",
    "smoking",
    "drinking",
    "pet_preference",
)

DIETS = ("pure_veg", "jain", "eggetarian", "non_veg", "vegan")
PETS = ("loves_pets", "cats_and_dogs_ok", "cats_ok", "dogs_ok", "no_pets", "allergic")
SMOKING = ("never", "outside_only", "permitted")

# Every answer the form offers. The API rejects anything else, so matching never compares
# values it doesn't know.
ALLOWED: Dict[str, tuple] = {
    "sleep_schedule": ("early_bird", "night_owl", "flexible", "rotational"),
    "work_arrangement": ("remote", "hybrid", "on_site", "shift_work"),
    "chore_philosophy": ("cook_maid", "shared_roster", "self_service"),
    "noise_tolerance": ("quiet_library", "moderate", "lively"),
    "lighting_preference": ("pitch_black", "dim", "flexible"),
    "guests_policy": ("rarely", "advance_notice", "occasional_weekends", "open_house"),
    "social_battery": ("introverted", "balanced", "extroverted"),
    "diet_preference": DIETS,
    "cooks_at_home": ("daily", "sometimes", "hires_cook", "orders_online"),
    "smoking": SMOKING,
    "drinking": ("teetotaler", "socially", "regular"),
    "pet_preference": PETS,
}

# Old quiz keys, renamed to the form's.
_RENAMED: Dict[str, str] = {"diet": "diet_preference", "pets": "pet_preference"}

# Old values (the quiz, the first onboarding wizard) -> the form's. Values not listed are kept.
_LEGACY_VALUES: Dict[str, Dict[str, str]] = {
    "diet_preference": {
        "vegetarian": "pure_veg", "veg_and_egg": "eggetarian", "omnivore": "non_veg",
        "pescatarian": "non_veg", "halal": "non_veg", "kosher": "non_veg",
    },
    "pet_preference": {"has_cat": "loves_pets", "has_dog": "loves_pets"},
    "smoking": {"allowed": "permitted", "regular": "permitted", "balcony_only": "outside_only"},
    "social_battery": {"moderate": "balanced"},
    "work_arrangement": {"office": "on_site"},
}


def canonical_value(key: str, value: Any) -> Any:
    """A filter or stored value in the form's vocabulary (old quiz values are converted)."""
    key = _RENAMED.get(key, key)
    if not isinstance(value, str):
        return value
    return _LEGACY_VALUES.get(key, {}).get(value, value)


def checked_value(key: str, value: Any) -> Any:
    """`canonical_value`, then refuse anything the form doesn't offer."""
    value = canonical_value(key, value)
    allowed = ALLOWED.get(_RENAMED.get(key, key))
    if allowed is not None and value not in allowed:
        raise ValueError(f"must be one of: {', '.join(allowed)}")
    return value


def canonical_traits(traits: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Traits in the form's keys and values; old quiz keys are renamed, never kept alongside."""
    src = dict(traits or {})
    out: Dict[str, Any] = {}
    for key, value in src.items():
        new_key = _RENAMED.get(key, key)
        if new_key != key and new_key in src:
            continue  # a form key always wins over the quiz key it replaces
        out[new_key] = canonical_value(new_key, value)
    return out


def traits_from_answers(answers: Any) -> Dict[str, Any]:
    """The profile copy of a saved lifestyle form (a LifestyleProfile or a mapping)."""
    get = answers.get if isinstance(answers, Mapping) else (lambda k: getattr(answers, k, None))
    return {key: get(key) for key in TRAIT_FIELDS if get(key) is not None}


# ---------------------------------------------------------------------------------------------
# Matching vector: 64 dimensions (settings.VECTOR_EMBEDDING_DIM), L2-normalised, compared by
# cosine distance in the first stage of recommendations. The slice layout and the numbers for
# values the old quiz also had are unchanged, so stored vectors stay comparable.
# ---------------------------------------------------------------------------------------------
_SLEEP = {"early_bird": 1.0, "flexible": 0.5, "rotational": 0.3, "night_owl": 0.0}
_SOCIAL = {"introverted": 0.2, "balanced": 0.7, "extroverted": 1.0}
_WORK = {"remote": 0.1, "hybrid": 0.5, "on_site": 0.9, "shift_work": 0.7}
_DIET = {"vegan": 1.0, "jain": 0.9, "pure_veg": 0.8, "eggetarian": 0.65, "non_veg": 0.4}
_SMOKING = {"never": 0.0, "outside_only": 0.5, "permitted": 1.0}
_PETS = {"no_pets": 0.0, "allergic": 0.0, "cats_ok": 0.4, "dogs_ok": 0.6, "cats_and_dogs_ok": 0.8,
         "loves_pets": 1.0}


def lifestyle_vector(traits: Optional[Mapping[str, Any]], dim: int = 64) -> List[float]:
    t = canonical_traits(traits)
    vec = [0.0] * dim

    def fill(start: int, end: int, value: float, wave) -> None:
        for i in range(start, min(end, dim)):
            vec[i] = value * wave(i)

    try:
        clean = float(t.get("cleanliness_level", 3)) / 5.0
    except (TypeError, ValueError):
        clean = 0.6
    fill(0, 8, _SLEEP.get(t.get("sleep_schedule"), 0.5), math.cos)
    fill(8, 16, clean, math.sin)
    fill(16, 24, _SOCIAL.get(t.get("social_battery"), 0.5), math.cos)
    fill(24, 32, _WORK.get(t.get("work_arrangement"), 0.5), math.sin)
    fill(32, 40, _DIET.get(t.get("diet_preference"), 0.5), math.cos)
    fill(40, 48, _SMOKING.get(t.get("smoking"), 0.0), math.sin)
    fill(48, 64, _PETS.get(t.get("pet_preference"), 0.5), lambda i: math.cos(i * 0.5))

    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec
