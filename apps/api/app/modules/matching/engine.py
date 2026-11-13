"""
Explainable 10-Dimension Compatibility Matching Engine
Deterministic scoring, factor-level explanations, dealbreaker enforcement, and algorithm versioning.
"""
import math
from typing import Dict, Any, Tuple, List, Optional

ALGORITHM_VERSION = "v1.0-india-heuristic"

# Configurable Dimension Weights (Sum = 1.0)
DIMENSION_WEIGHTS = {
    "working_schedule": 0.15,
    "sleep_schedule": 0.15,
    "budget": 0.15,
    "cleanliness": 0.12,
    "lifestyle": 0.12,
    "noise_and_lighting": 0.10,
    "guests_and_social": 0.07,
    "food_and_cooking": 0.05,
    "professional_domain": 0.05,
    "location": 0.04,
}

def cosine_similarity(v1: list, v2: list) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.5
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.5
    sim = dot / (norm1 * norm2)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0))

def score_working_schedule(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    w1 = t1.get("work_arrangement", "hybrid")
    w2 = t2.get("work_arrangement", "hybrid")
    if w1 == w2:
        return 100, f"Both have identical {w1} work schedules."
    if "shift_work" in (w1, w2):
        return 50, "One flatmate has rotational shift work; schedule coordination recommended."
    if "remote" in (w1, w2) and "on_site" in (w1, w2):
        return 75, "Complementary occupancy: one works from home while one is on-site."
    return 85, f"Compatible working modes ({w1} & {w2})."

def score_sleep_schedule(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    s1 = t1.get("sleep_schedule", "flexible")
    s2 = t2.get("sleep_schedule", "flexible")
    if s1 == s2:
        return 95, f"Harmonious sleep cycles: both are {s1}s."
    if "flexible" in (s1, s2):
        return 80, "Flexible sleeping hours accommodate differences smoothly."
    # Opposite schedules: early_bird vs night_owl
    return 40, "Contrasting sleep cycles: one early riser and one night owl."

def score_budget(user_b: Tuple[int, int], target_b: Tuple[int, int]) -> Tuple[int, str]:
    overlap_min = max(user_b[0], target_b[0])
    overlap_max = min(user_b[1], target_b[1])
    if overlap_max >= overlap_min:
        overlap_range = overlap_max - overlap_min
        user_range = max(1, user_b[1] - user_b[0])
        score = min(100, max(50, int((overlap_range / user_range) * 100)))
        return score, f"Solid budget overlap: ₹{overlap_min:,} - ₹{overlap_max:,}/month."
    diff = overlap_min - overlap_max
    score = max(10, 100 - (diff // 500) * 10)
    return score, f"Budget ranges diverge by approx ₹{diff:,}."

def score_cleanliness(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    cleanliness_map = {
        "very_clean": 5,
        "clean": 4,
        "moderate": 3,
        "relaxed": 2,
        "messy": 1,
    }
    raw_c1 = t1.get("cleanliness_level", 3)
    raw_c2 = t2.get("cleanliness_level", 3)

    def _parse_level(val: Any) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            if val.lower() in cleanliness_map:
                return cleanliness_map[val.lower()]
            try:
                return int(val)
            except ValueError:
                pass
        return 3

    c1 = _parse_level(raw_c1)
    c2 = _parse_level(raw_c2)
    diff = abs(c1 - c2)
    score = max(0, 100 - diff * 25)
    chore1 = t1.get("chore_philosophy", "shared_roster")
    chore2 = t2.get("chore_philosophy", "shared_roster")
    if chore1 == chore2:
        score = min(100, score + 5)
    return score, f"Cleanliness expectations ({c1}/5 vs {c2}/5)."

def score_lifestyle(t1: Dict[str, Any], t2: Dict[str, Any], vector_sim: float) -> Tuple[int, str]:
    smk1 = t1.get("smoking", "never")
    smk2 = t2.get("smoking", "never")
    drk1 = t1.get("drinking", "socially")
    drk2 = t2.get("drinking", "socially")

    base = int(vector_sim * 100)
    if smk1 == smk2 and drk1 == drk2:
        base = min(100, base + 10)
    return base, "Harmonious lifestyle and substance habits."

def score_noise_lighting(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    n1 = t1.get("noise_tolerance", "moderate")
    n2 = t2.get("noise_tolerance", "moderate")
    l1 = t1.get("lighting_preference", "dim")
    l2 = t2.get("lighting_preference", "dim")

    score = 80
    if n1 == n2:
        score += 10
    if l1 == l2:
        score += 10
    if t1.get("instrument_or_music") and n2 == "quiet_library":
        score -= 30
    return max(20, min(100, score)), "Noise tolerance and bedroom environment alignment."

def score_guests_social(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    g1 = t1.get("guests_policy", "occasional_weekends")
    g2 = t2.get("guests_policy", "occasional_weekends")
    sb1 = t1.get("social_battery", "balanced")
    sb2 = t2.get("social_battery", "balanced")

    score = 85
    if g1 == g2:
        score += 10
    if sb1 == sb2:
        score += 5
    if "open_house" in (g1, g2) and "rarely" in (g1, g2):
        score -= 35
    return max(25, min(100, score)), "Guest visits policy and household social interaction."

def score_food_cooking(t1: Dict[str, Any], t2: Dict[str, Any]) -> Tuple[int, str]:
    d1 = t1.get("diet_preference", "omnivore")
    d2 = t2.get("diet_preference", "omnivore")
    cook1 = t1.get("cooks_at_home", "sometimes")
    cook2 = t2.get("cooks_at_home", "sometimes")

    score = 85
    if d1 == d2:
        score += 15
    elif "pure_veg" in (d1, d2) and "non_veg" in (d1, d2):
        score -= 20
    if cook1 == cook2:
        score += 5
    return max(30, min(100, score)), f"Kitchen & dietary compatibility ({d1} & {d2})."

def score_professional_domain(occ1: Optional[str], occ2: Optional[str], dom1: Optional[str], dom2: Optional[str]) -> Tuple[int, str]:
    if dom1 and dom2 and dom1.lower() == dom2.lower():
        return 95, f"Shared professional domain ({dom1}); similar work routines."
    if occ1 and occ2 and occ1.lower() == occ2.lower():
        return 90, f"Peer profession ({occ1})."
    return 75, "Diverse professional backgrounds."

def score_location(pref_locs1: List[str], pref_locs2: List[str]) -> Tuple[int, str]:
    if not pref_locs1 or not pref_locs2:
        return 70, "Open location flexibility."
    set1 = {loc.strip().lower() for loc in pref_locs1}
    set2 = {loc.strip().lower() for loc in pref_locs2}
    common = set1.intersection(set2)
    if common:
        loc_str = ", ".join(list(common)[:2]).title()
        return 95, f"Mutual preference for {loc_str}."
    return 50, "Different preferred target neighborhoods."

def evaluate_dealbreakers(
    user_traits: Dict[str, Any],
    target_traits: Dict[str, Any],
    user_dealbreakers: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, List[str]]:
    conflicts = []

    # 1. Smoking dealbreaker
    if user_traits.get("smoking") == "never" and target_traits.get("smoking") in ("permitted", "allowed"):
        conflicts.append("Smoking inside home conflicts with non-smoker policy.")
    if target_traits.get("smoking") == "never" and user_traits.get("smoking") in ("permitted", "allowed"):
        conflicts.append("Candidate requires a strictly smoke-free household.")

    # 2. Kitchen / Diet dealbreaker
    if user_traits.get("diet_preference") in ("pure_veg", "jain") and not user_traits.get("non_veg_cooking_allowed", True):
        if target_traits.get("diet_preference") == "non_veg":
            conflicts.append("Non-vegetarian cooking conflict with pure veg kitchen restriction.")

    # 3. Custom user dealbreaker rules
    if user_dealbreakers:
        for db in user_dealbreakers:
            rule = db.get("rule_key")
            is_strict = db.get("is_strict", True)
            if is_strict:
                if rule == "no_smoking_inside" and target_traits.get("smoking") in ("permitted", "allowed"):
                    conflicts.append("Strict rule: No smoking inside the flat.")
                elif rule == "pure_veg_kitchen_only" and target_traits.get("diet_preference") == "non_veg":
                    conflicts.append("Strict rule: Pure vegetarian kitchen only.")
                elif rule == "no_pets_allowed" and target_traits.get("pet_preference") in ("loves_pets", "has_cat", "has_dog"):
                    conflicts.append("Strict rule: No pets permitted.")

    return len(conflicts) == 0, conflicts

def compute_10_dimension_compatibility(
    user_traits: Dict[str, Any],
    target_traits: Dict[str, Any],
    user_budget: Tuple[int, int],
    target_budget: Tuple[int, int],
    user_occupation: Optional[str] = None,
    target_occupation: Optional[str] = None,
    user_domain: Optional[str] = None,
    target_domain: Optional[str] = None,
    user_preferred_locs: Optional[List[str]] = None,
    target_preferred_locs: Optional[List[str]] = None,
    vector_sim: float = 0.5,
    user_dealbreakers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    factors = {}
    explanations = {}

    s_work, exp_work = score_working_schedule(user_traits, target_traits)
    factors["working_schedule"] = s_work
    explanations["working_schedule"] = exp_work

    s_sleep, exp_sleep = score_sleep_schedule(user_traits, target_traits)
    factors["sleep_schedule"] = s_sleep
    explanations["sleep_schedule"] = exp_sleep

    s_bud, exp_bud = score_budget(user_budget, target_budget)
    factors["budget"] = s_bud
    explanations["budget"] = exp_bud

    s_clean, exp_clean = score_cleanliness(user_traits, target_traits)
    factors["cleanliness"] = s_clean
    explanations["cleanliness"] = exp_clean

    s_life, exp_life = score_lifestyle(user_traits, target_traits, vector_sim)
    factors["lifestyle"] = s_life
    explanations["lifestyle"] = exp_life

    s_nl, exp_nl = score_noise_lighting(user_traits, target_traits)
    factors["noise_and_lighting"] = s_nl
    explanations["noise_and_lighting"] = exp_nl

    s_gs, exp_gs = score_guests_social(user_traits, target_traits)
    factors["guests_and_social"] = s_gs
    explanations["guests_and_social"] = exp_gs

    s_fc, exp_fc = score_food_cooking(user_traits, target_traits)
    factors["food_and_cooking"] = s_fc
    explanations["food_and_cooking"] = exp_fc

    s_pd, exp_pd = score_professional_domain(user_occupation, target_occupation, user_domain, target_domain)
    factors["professional_domain"] = s_pd
    explanations["professional_domain"] = exp_pd

    s_loc, exp_loc = score_location(user_preferred_locs or [], target_preferred_locs or [])
    factors["location"] = s_loc
    explanations["location"] = exp_loc

    weighted_score = sum(factors[k] * DIMENSION_WEIGHTS[k] for k in DIMENSION_WEIGHTS)

    cleared, conflicts = evaluate_dealbreakers(user_traits, target_traits, user_dealbreakers)
    if not cleared:
        weighted_score = min(weighted_score, 30.0)

    return {
        "overall_score": round(weighted_score, 1),
        "factors": factors,
        "explanations": explanations,
        "dealbreakers_cleared": cleared,
        "conflicts": conflicts,
        "algorithm_version": ALGORITHM_VERSION,
    }

def compute_compatibility_breakdown(
    user_traits: Dict[str, Any],
    target_traits: Dict[str, Any],
    user_budget: Tuple[int, int],
    target_budget: Tuple[int, int],
    vector_sim: float,
) -> Dict[str, Any]:
    """Backwards compatible wrapper for existing callers/tests."""
    res = compute_10_dimension_compatibility(
        user_traits=user_traits,
        target_traits=target_traits,
        user_budget=user_budget,
        target_budget=target_budget,
        vector_sim=vector_sim,
    )
    return {
        "overall_score": res["overall_score"],
        "lifestyle_score": res["factors"]["lifestyle"],
        "cleanliness_alignment": res["factors"]["cleanliness"],
        "schedule_alignment": res["factors"]["sleep_schedule"],
        "social_alignment": res["factors"]["guests_and_social"],
        "budget_alignment": res["factors"]["budget"],
        "dealbreakers_cleared": res["dealbreakers_cleared"],
        "shared_interests": ["Harmonious habits", "Coordinated schedules"],
        "factors": res["factors"],
        "explanations": res["explanations"],
        "conflicts": res["conflicts"],
        "algorithm_version": res["algorithm_version"],
    }
