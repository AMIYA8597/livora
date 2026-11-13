from app.modules.matching.engine import cosine_similarity, compute_compatibility_breakdown
from app.modules.profiles.service import compute_lifestyle_vector
from app.modules.profiles.schemas import LifestyleTraitsSchema

def test_cosine_similarity_identical():
    v1 = [0.5, 0.5, 0.5, 0.5]
    sim = cosine_similarity(v1, v1)
    assert round(sim, 2) == 1.0

def test_lifestyle_vector_generation():
    traits = LifestyleTraitsSchema(
        sleep_schedule="early_bird",
        cleanliness_level=5,
        social_battery="moderate",
        work_arrangement="hybrid",
        diet="vegan",
        smoking="never",
        pets="cats_ok",
        guests_policy="weekends",
    )
    vec = compute_lifestyle_vector(traits)
    assert len(vec) == 64
    # Check normalization
    norm = sum(x * x for x in vec)
    assert abs(norm - 1.0) < 0.001

def test_compatibility_scoring_dealbreaker():
    user_traits = {"smoking": "never", "cleanliness_level": 5}
    target_traits = {"smoking": "allowed", "cleanliness_level": 2}
    result = compute_compatibility_breakdown(
        user_traits=user_traits,
        target_traits=target_traits,
        user_budget=(1000, 1500),
        target_budget=(1000, 1500),
        vector_sim=0.9,
    )
    assert result["dealbreakers_cleared"] is False
    assert result["overall_score"] <= 40.0
