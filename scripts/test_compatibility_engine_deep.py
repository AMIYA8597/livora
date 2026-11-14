"""
Deep Empirical Compatibility Engine Validation Suite
Evaluates deterministic 10-dimension matching engine across edge cases,
boundary conditions, and synthetic profiles.
"""
import sys
sys.path.insert(0, "apps/api")
from app.modules.matching.engine import (
    DIMENSION_WEIGHTS,
    compute_10_dimension_compatibility,
    ALGORITHM_VERSION,
)

def run_tests():
    print(f"Algorithm Version: {ALGORITHM_VERSION}")

    # 1. Weights Sum Test
    weight_sum = sum(DIMENSION_WEIGHTS.values())
    print(f"1. Total Weight Sum: {weight_sum:.6f}")
    assert abs(weight_sum - 1.0) < 1e-6, f"Weights do not sum to 1.0: {weight_sum}"
    print("   -> Weight sum equals 100%: PASS")

    # 2. Perfect Compatibility
    t_perfect = {
        "work_arrangement": "hybrid",
        "sleep_schedule": "flexible",
        "cleanliness_level": 4,
        "chore_philosophy": "shared_roster",
        "noise_tolerance": "moderate",
        "lighting_preference": "dim",
        "guests_policy": "occasional_weekends",
        "social_battery": "balanced",
        "diet_preference": "vegetarian",
        "cooks_at_home": "sometimes",
        "smoking": "never",
        "drinking": "socially",
    }
    res_perfect = compute_10_dimension_compatibility(
        user_traits=t_perfect,
        target_traits=t_perfect,
        user_budget=(25000, 35000),
        target_budget=(25000, 35000),
        user_occupation="Data Scientist",
        target_occupation="Data Scientist",
        user_domain="Technology",
        target_domain="Technology",
        user_preferred_locs=["Koramangala"],
        target_preferred_locs=["Koramangala"],
        vector_sim=1.0,
    )
    score_p = res_perfect["overall_score"]
    print(f"2. Perfectly Compatible Score: {score_p}")
    assert score_p >= 90.0, f"Expected score >= 90, got {score_p}"
    assert res_perfect["dealbreakers_cleared"] is True
    print("   -> Perfectly compatible profile test: PASS")

    # 3. Poorly Compatible (Conflicting everything)
    t_poor_user = {
        "work_arrangement": "remote",
        "sleep_schedule": "early_bird",
        "cleanliness_level": 5,
        "chore_philosophy": "strict_individual",
        "noise_tolerance": "quiet_library",
        "guests_policy": "rarely",
        "diet_preference": "pure_veg",
        "smoking": "never",
        "drinking": "never",
    }
    t_poor_target = {
        "work_arrangement": "shift_work",
        "sleep_schedule": "night_owl",
        "cleanliness_level": 1,
        "chore_philosophy": "relaxed",
        "noise_tolerance": "lively_parties",
        "guests_policy": "open_house",
        "diet_preference": "non_veg",
        "smoking": "permitted",
        "drinking": "frequently",
    }
    res_poor = compute_10_dimension_compatibility(
        user_traits=t_poor_user,
        target_traits=t_poor_target,
        user_budget=(10000, 15000),
        target_budget=(50000, 80000),
        user_occupation="Researcher",
        target_occupation="DJ",
        user_domain="Academia",
        target_domain="Entertainment",
        user_preferred_locs=["Whitefield"],
        target_preferred_locs=["Indiranagar"],
        vector_sim=0.1,
    )
    score_poor = res_poor["overall_score"]
    print(f"3. Poorly Compatible Score: {score_poor}")
    assert score_poor <= 30.0, f"Expected capped score <= 30 due to dealbreakers, got {score_poor}"
    assert res_poor["dealbreakers_cleared"] is False
    assert len(res_poor["conflicts"]) > 0
    print(f"   -> Detected conflicts: {res_poor['conflicts']}")
    print("   -> Poor compatibility & dealbreaker cap: PASS")

    # 4. Missing Traits (Default Fallbacks)
    res_empty = compute_10_dimension_compatibility(
        user_traits={},
        target_traits={},
        user_budget=(20000, 30000),
        target_budget=(20000, 30000),
        vector_sim=0.5,
    )
    score_empty = res_empty["overall_score"]
    print(f"4. Symmetric Empty Traits Fallback Score: {score_empty}")
    assert 50.0 <= score_empty <= 100.0, f"Unexpected empty traits score: {score_empty}"
    assert res_empty["dealbreakers_cleared"] is True

    # Asymmetric empty traits
    res_asym = compute_10_dimension_compatibility(
        user_traits=t_perfect,
        target_traits={},
        user_budget=(20000, 30000),
        target_budget=(15000, 22000),
        vector_sim=0.5,
    )
    score_asym = res_asym["overall_score"]
    print(f"4b. Asymmetric Incomplete Profile Score: {score_asym}")
    assert 50.0 <= score_asym <= 95.0, f"Unexpected asymmetric score: {score_asym}"
    print("   -> Missing traits graceful fallback: PASS")

    # 5. Extreme Budget Divergence
    res_budget_diff = compute_10_dimension_compatibility(
        user_traits=t_perfect,
        target_traits=t_perfect,
        user_budget=(5000, 8000),
        target_budget=(70000, 120000),
        vector_sim=0.9,
    )
    print(f"5. Extreme Budget Divergence Score: {res_budget_diff['factors']['budget']}")
    assert res_budget_diff["factors"]["budget"] <= 20
    print("   -> Budget divergence penalty: PASS")

    # 6. Custom User Dealbreaker Rules
    user_dbs = [
        {"rule_key": "no_smoking_inside", "is_strict": True},
        {"rule_key": "pure_veg_kitchen_only", "is_strict": True},
        {"rule_key": "no_pets_allowed", "is_strict": True},
    ]
    target_smoker = {"smoking": "permitted", "diet_preference": "vegetarian"}
    res_db = compute_10_dimension_compatibility(
        user_traits={"smoking": "never", "diet_preference": "pure_veg"},
        target_traits=target_smoker,
        user_budget=(20000, 30000),
        target_budget=(20000, 30000),
        user_dealbreakers=user_dbs,
    )
    assert res_db["dealbreakers_cleared"] is False
    assert res_db["overall_score"] <= 30.0
    print(f"6. Strict custom dealbreaker evaluation: PASS (Capped at {res_db['overall_score']}%)")

    # 7. Normalization Bounds across 100 randomized inputs
    import random
    for _ in range(100):
        b1 = (random.randint(5000, 50000), random.randint(50000, 100000))
        b2 = (random.randint(5000, 50000), random.randint(50000, 100000))
        sim = random.random()
        res_rand = compute_10_dimension_compatibility(
            user_traits={"cleanliness_level": random.randint(1, 5)},
            target_traits={"cleanliness_level": random.randint(1, 5)},
            user_budget=b1,
            target_budget=b2,
            vector_sim=sim,
        )
        s = res_rand["overall_score"]
        assert 0.0 <= s <= 100.0, f"Score out of bounds [0, 100]: {s}"

    print("7. 100 Random permutations score bounds [0.0, 100.0]: PASS")
    print("\n=== COMPATIBILITY ENGINE DEEP VALIDATION PASSED 100% ===")

if __name__ == "__main__":
    run_tests()
