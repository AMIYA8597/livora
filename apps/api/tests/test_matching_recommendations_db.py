"""
Recommendation retrieval against a real PostgreSQL database (no mocks).

Fixtures use a budget band no other test uses (~9M INR) so that the candidate pool contains
only the profiles created here, even though the shared test database accumulates rows.
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ForbiddenException
from app.modules.matching.models import MutualMatch
from app.modules.matching.service import MatchingService
from app.modules.moderation.models import UserBlock
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting

BAND_MIN, BAND_MAX = 9_000_000, 9_100_000
DIM = 64


def _vector(seed: float) -> list:
    return [((i % 7) + seed) / 10.0 for i in range(DIM)]


async def _make_user(session, label, *, visibility="public", active=True, budget=(BAND_MIN, BAND_MAX), phone=None):
    user = User(
        id=uuid4(),
        email=f"rec-{label}-{uuid4().hex[:8]}@example.test",
        hashed_password="x",
        full_name=f"Rec {label}",
        phone_number=phone,
        is_active=active,
    )
    session.add(user)
    await session.flush()
    session.add(Profile(
        user_id=user.id,
        display_name=f"Rec {label}",
        budget_min=budget[0],
        budget_max=budget[1],
        lifestyle_vector=_vector(1.0),
        lifestyle_traits={},
        preferred_locations=[],
    ))
    session.add(UserPrivacySetting(user_id=user.id, profile_visibility=visibility))
    await session.flush()
    return user.id


@pytest.fixture
async def world():
    async with AsyncSessionLocal() as session:
        ids = {}
        ids["me"] = await _make_user(session, "me")
        ids["good"] = await _make_user(session, "good", phone="+919876543210")
        ids["blocked_by_me"] = await _make_user(session, "blocked-by-me")
        ids["blocks_me"] = await _make_user(session, "blocks-me")
        ids["private"] = await _make_user(session, "private", visibility="private")
        ids["matched_only_no_match"] = await _make_user(session, "mo-nomatch", visibility="matched_only")
        ids["matched_only_matched"] = await _make_user(session, "mo-matched", visibility="matched_only")
        ids["inactive"] = await _make_user(session, "inactive", active=False)
        ids["budget_far"] = await _make_user(session, "budget-far", budget=(100, 200))

        session.add_all([
            UserBlock(user_id=ids["me"], blocked_user_id=ids["blocked_by_me"]),
            UserBlock(user_id=ids["blocks_me"], blocked_user_id=ids["me"]),
            MutualMatch(
                user_one_id=ids["me"], user_two_id=ids["matched_only_matched"],
                compatibility_score=80.0, status="matched", matched_at=datetime.now(timezone.utc),
            ),
        ])
        await session.commit()

        yield session, ids

        await session.rollback()
        await session.execute(delete(User).where(User.id.in_(list(ids.values()))))
        await session.commit()


async def test_recommendations_apply_all_retrieval_filters(world):
    session, ids = world
    recs = await MatchingService(session).get_user_recommendations(ids["me"], limit=50)
    returned = {r.profile.user_id for r in recs}

    assert ids["good"] in returned
    assert ids["matched_only_matched"] in returned
    for excluded in ("me", "blocked_by_me", "blocks_me", "private",
                     "matched_only_no_match", "inactive", "budget_far"):
        assert ids[excluded] not in returned, f"{excluded} must not be recommended"

    scores = [r.match_score.overall_score for r in recs]
    assert scores == sorted(scores, reverse=True)


async def test_recommendations_mask_phone_numbers(world):
    session, ids = world
    recs = await MatchingService(session).get_user_recommendations(ids["me"], limit=50)
    good = next(r for r in recs if r.profile.user_id == ids["good"])
    assert good.profile.phone_number == "+91******10"


async def test_private_profile_does_not_break_recommendations(world):
    """Regression: one private candidate used to raise ForbiddenException for the whole list."""
    session, ids = world
    recs = await MatchingService(session).get_user_recommendations(ids["me"], limit=50)
    assert len(recs) >= 2


@pytest.mark.parametrize("target", ["blocked_by_me", "blocks_me"])
async def test_cannot_interact_with_blocked_users(world, target):
    session, ids = world
    with pytest.raises(ForbiddenException):
        await MatchingService(session).record_interaction(ids["me"], ids[target], "like")
