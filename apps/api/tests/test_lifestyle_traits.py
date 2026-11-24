"""
Lifestyle answers reach matching: one vocabulary (app/modules/lifestyle/traits.py), the form's
save rewrites the profile copy that matching, filters, embeddings and smart replies read, and
old quiz/wizard values are converted (or refused) at the edge.
"""
import math
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.ml.embeddings import profile_text
from app.ml.indexing import EMBEDDING_REFRESH_EVENT
from app.modules.lifestyle.schemas import LifestyleCreateOrUpdate
from app.modules.lifestyle.traits import (
    ALLOWED,
    canonical_traits,
    canonical_value,
    checked_value,
    lifestyle_vector,
    traits_from_answers,
)
from app.modules.messaging.models import OutboxEvent
from app.modules.profiles.models import Profile
from app.modules.users.models import User

API = settings.API_V1_PREFIX
BUDGET = (991_000, 994_000)  # unique range: only this file's profiles match each other


# --------------------------------------------------------------------------- unit


def test_quiz_keys_are_renamed_and_values_converted():
    assert canonical_traits({"diet": "vegetarian", "pets": "has_cat", "smoking": "allowed",
                             "social_battery": "moderate", "work_arrangement": "office"}) == {
        "diet_preference": "pure_veg", "pet_preference": "loves_pets", "smoking": "permitted",
        "social_battery": "balanced", "work_arrangement": "on_site",
    }


def test_a_form_key_wins_over_the_quiz_key_it_replaces():
    assert canonical_traits({"diet": "omnivore", "diet_preference": "jain"}) == {"diet_preference": "jain"}
    assert canonical_traits(None) == {}


def test_filter_values_accept_both_vocabularies():
    assert canonical_value("diet", "vegetarian") == "pure_veg"
    assert canonical_value("diet_preference", "pure_veg") == "pure_veg"
    assert canonical_value("pets", "has_dog") == "loves_pets"
    assert canonical_value("cleanliness_level", 4) == 4


def test_unknown_answers_are_refused():
    assert checked_value("diet_preference", "omnivore") == "non_veg"
    with pytest.raises(ValueError, match="pure_veg, jain"):
        checked_value("diet_preference", "keto")


def test_the_form_schema_converts_old_values_and_refuses_unknown_ones():
    answers = LifestyleCreateOrUpdate(diet_preference="veg_and_egg", smoking="balcony_only", work_arrangement="office")
    assert (answers.diet_preference, answers.smoking, answers.work_arrangement) == ("eggetarian", "outside_only", "on_site")
    for field in ALLOWED:
        with pytest.raises(ValidationError):
            LifestyleCreateOrUpdate(**{field: "not-a-real-answer"})
    # Every default is itself an allowed answer.
    defaults = LifestyleCreateOrUpdate()
    for field, allowed in ALLOWED.items():
        assert getattr(defaults, field) in allowed, field


def test_vector_is_unit_length_and_old_and_new_vocabularies_agree():
    old = {"sleep_schedule": "night_owl", "cleanliness_level": 4, "diet": "vegetarian", "smoking": "allowed", "pets": "has_cat"}
    new = canonical_traits(old)
    vec = lifestyle_vector(new)
    assert len(vec) == 64
    assert math.isclose(sum(x * x for x in vec), 1.0, rel_tol=1e-9)
    assert lifestyle_vector(old) == vec
    # Diet now moves the vector: a jain and a non-veg profile differ.
    assert lifestyle_vector({**new, "diet_preference": "jain"}) != lifestyle_vector({**new, "diet_preference": "non_veg"})


def test_traits_from_answers_copies_only_form_fields():
    answers = LifestyleCreateOrUpdate(diet_preference="jain", custom_notes="hi").model_dump()
    traits = traits_from_answers(answers)
    assert traits["diet_preference"] == "jain"
    assert "custom_notes" not in traits and "wake_time_typical" not in traits


def test_embedding_text_reads_form_answers():
    profile = Profile(display_name="X", lifestyle_traits={"diet_preference": "jain", "pet_preference": "allergic",
                                                          "smoking": "permitted"})
    text = profile_text(profile)
    assert "jain vegetarian" in text and "allergic to pets" in text and "smoker" in text


# --------------------------------------------------------------------------- database


def _auth(user_id) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user_id), roles=['seeker'])}"}


@pytest.fixture
async def people():
    ids = {n: uuid4() for n in ("viewer", "quiz", "former")}
    async with AsyncSessionLocal() as s:
        for n, uid in ids.items():
            s.add(User(id=uid, email=f"lt-{n}-{uuid4().hex[:6]}@example.com", hashed_password="x",
                       full_name=n.title(), is_active=True))
        await s.flush()
        old = {"sleep_schedule": "night_owl", "diet": "omnivore", "pets": "has_dog", "smoking": "allowed"}
        for n, uid in ids.items():
            s.add(Profile(user_id=uid, display_name=n.title(), budget_min=BUDGET[0], budget_max=BUDGET[1],
                          lifestyle_traits=old if n != "viewer" else {}, lifestyle_vector=[0.0] * 64,
                          preferred_locations=[]))
        await s.commit()
    yield ids
    async with AsyncSessionLocal() as s:
        await s.execute(delete(OutboxEvent).where(
            OutboxEvent.event_type == EMBEDDING_REFRESH_EVENT,
            OutboxEvent.payload["entity_id"].astext.in_([str(i) for i in ids.values()]),
        ))
        await s.execute(delete(User).where(User.id.in_(list(ids.values()))))
        await s.commit()


@pytest.mark.asyncio
async def test_saving_the_form_updates_what_matching_reads(async_client, people):
    uid = people["former"]
    res = await async_client.put(f"{API}/lifestyle/me", headers=_auth(uid), json={
        "sleep_schedule": "early_bird", "cleanliness_level": 5, "work_arrangement": "remote",
        "diet_preference": "vegetarian", "non_veg_cooking_allowed": False, "smoking": "never",
        "pet_preference": "allergic", "social_battery": "introverted", "noise_tolerance": "quiet_library",
        "guests_policy": "rarely",
    })
    assert res.status_code == 200, res.text
    assert res.json()["diet_preference"] == "pure_veg"

    async with AsyncSessionLocal() as s:
        profile = (await s.execute(select(Profile).where(Profile.user_id == uid))).scalar_one()
        traits = profile.lifestyle_traits
        assert traits["diet_preference"] == "pure_veg"
        assert traits["pet_preference"] == "allergic"
        assert traits["non_veg_cooking_allowed"] is False
        assert "diet" not in traits and "pets" not in traits
        assert profile.lifestyle_vector == pytest.approx(lifestyle_vector(traits))
        queued = (await s.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == EMBEDDING_REFRESH_EVENT,
            OutboxEvent.payload["entity_id"].astext == str(uid),
        ))).scalars().all()
        assert queued

    bad = await async_client.put(f"{API}/lifestyle/me", headers=_auth(uid), json={"diet_preference": "keto"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_flatmate_filters_use_form_answers_in_either_vocabulary(async_client, people):
    await async_client.put(f"{API}/lifestyle/me", headers=_auth(people["former"]),
                           json={"diet_preference": "pure_veg", "pet_preference": "no_pets", "smoking": "never"})
    async with AsyncSessionLocal() as s:
        quiz = (await s.execute(select(Profile).where(Profile.user_id == people["quiz"]))).scalar_one()
        quiz.lifestyle_traits = canonical_traits(quiz.lifestyle_traits)
        await s.commit()

    async def found(**params):
        res = await async_client.get(f"{API}/flatmates/search", headers=_auth(people["viewer"]),
                                     params={"min_budget": BUDGET[0], "max_budget": BUDGET[1], **params})
        assert res.status_code == 200, res.text
        return {c["user_id"] for c in res.json()}

    former, quiz = str(people["former"]), str(people["quiz"])
    assert await found(diet="pure_veg") == {former}
    assert await found(diet="vegetarian") == {former}  # old filter value still works
    assert await found(diet="omnivore") == {quiz}
    assert await found(pets="no_pets") == {former}
    assert await found(pets="has_dog") == {quiz}
    assert await found(smoking="allowed") == {quiz}
