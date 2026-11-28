from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, text
from app.modules.notifications import events as notification_events
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting
from app.modules.lifestyle.models import UserDealbreaker
from app.modules.matching.models import MatchInteraction, MutualMatch
from app.modules.matching.engine import (
    cosine_similarity,
    compute_10_dimension_compatibility,
    ALGORITHM_VERSION,
)
from app.modules.matching.schemas import (
    FlatmateMatchResponse,
    ScoreBreakdownSchema,
    MatchInteractionResponse,
    MutualMatchItemResponse,
)
from app.modules.profiles.service import ProfileService, build_profile_response
from app.core.exceptions import NotFoundException, BadRequestException, ForbiddenException
from app.modules.moderation.models import UserBlock
from app.ml.embeddings import cosine, get_embedder
from app.ml.models import ContentEmbedding
from app.ml.ranker import active_ranker, pair_features
from app.modules.billing.entitlements import ensure_can_like, get_entitlements

# Retrieval stage size: candidates fetched by SQL before exact re-ranking in Python.
CANDIDATE_POOL_SIZE = 200
# Budget ranges may miss each other by up to 25% and still be considered.
BUDGET_TOLERANCE = 0.25
# None = not yet probed; set by MatchingService._has_vector_index().
_VECTOR_SEARCH_AVAILABLE: Optional[bool] = None

VALID_INTERACTION_ACTIONS = {"like", "pass", "save", "super_like"}
# People you passed on come back after this long; likes and saves never reappear.
PASS_RESURFACE_AFTER = timedelta(days=30)

class MatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _has_vector_index(self) -> bool:
        """True when migration 003 created the pgvector `lifestyle_embedding` column (cached per process)."""
        global _VECTOR_SEARCH_AVAILABLE
        if _VECTOR_SEARCH_AVAILABLE is None:
            res = await self.db.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'profiles' AND column_name = 'lifestyle_embedding'"
            ))
            _VECTOR_SEARCH_AVAILABLE = res.scalar_one_or_none() is not None
        return bool(_VECTOR_SEARCH_AVAILABLE)

    async def get_user_recommendations(self, user_id: UUID, limit: int = 10) -> List[FlatmateMatchResponse]:
        """
        Two-stage recommender:
          1. Retrieval (SQL): exclude self, blocked/blocking users, inactive accounts, profiles the
             requester may not see, and clearly incompatible budgets; order by pgvector cosine
             distance via the HNSW index when available. One round trip, no per-candidate queries.
          2. Ranking (Python): exact 10-dimension compatibility score + dealbreakers on the pool.
        """
        profile_service = ProfileService(self.db)
        my_profile = await profile_service.get_by_user_id(user_id)
        if not my_profile:
            raise NotFoundException("Your profile has not been set up yet. Please complete your profile.")

        db_query = select(UserDealbreaker).where(UserDealbreaker.user_id == user_id)
        dbs_res = await self.db.execute(db_query)
        dealbreakers = [{"rule_key": d.rule_key, "is_strict": d.is_strict, "expected_value": d.expected_value} for d in dbs_res.scalars().all()]

        blocked_q = select(UserBlock.blocked_user_id).where(UserBlock.user_id == user_id)
        blocker_q = select(UserBlock.user_id).where(UserBlock.blocked_user_id == user_id)
        is_mutual_match = (
            select(MutualMatch.id)
            .where(
                or_(
                    and_(MutualMatch.user_one_id == user_id, MutualMatch.user_two_id == Profile.user_id),
                    and_(MutualMatch.user_one_id == Profile.user_id, MutualMatch.user_two_id == user_id),
                ),
                MutualMatch.status == "matched",
            )
            .exists()
        )
        visibility = func.coalesce(UserPrivacySetting.profile_visibility, "public")
        already_acted = select(MatchInteraction.target_user_id).where(
            MatchInteraction.user_id == user_id,
            or_(
                MatchInteraction.action != "pass",
                MatchInteraction.created_at >= datetime.now(timezone.utc) - PASS_RESURFACE_AFTER,
            ),
        )

        # Budget pre-filter with tolerance: ranges must overlap once widened by BUDGET_TOLERANCE.
        my_min = my_profile.budget_min or 0
        my_max = my_profile.budget_max or 10**9
        widened_min = int(my_min * (1 - BUDGET_TOLERANCE))
        widened_max = int(my_max * (1 + BUDGET_TOLERANCE))

        stmt = (
            select(Profile, User, UserPrivacySetting)
            .join(User, User.id == Profile.user_id)
            .outerjoin(UserPrivacySetting, UserPrivacySetting.user_id == Profile.user_id)
            .where(
                Profile.user_id != user_id,
                ~Profile.user_id.in_(blocked_q),
                ~Profile.user_id.in_(blocker_q),
                ~Profile.user_id.in_(already_acted),
                User.is_active.is_(True),
                or_(visibility == "public", and_(visibility == "matched_only", is_mutual_match)),
                Profile.budget_min <= widened_max,
                Profile.budget_max >= widened_min,
            )
        )

        my_vector = list(my_profile.lifestyle_vector) if my_profile.lifestyle_vector is not None else []
        has_signal = any(abs(x) > 0 for x in my_vector)
        if has_signal and await self._has_vector_index():
            stmt = stmt.order_by(
                text("profiles.lifestyle_embedding <=> CAST(:query_vec AS vector) NULLS LAST")
            ).params(query_vec="[" + ",".join(f"{x:.6f}" for x in my_vector) + "]")
        else:
            stmt = stmt.order_by(Profile.updated_at.desc().nullslast())
        stmt = stmt.limit(CANDIDATE_POOL_SIZE)

        rows = (await self.db.execute(stmt)).all()

        bios = await self._bio_embeddings([user_id, *(cand.user_id for cand, _, _ in rows)])
        my_bio = bios.get(user_id)
        ranker = await active_ranker(self.db)

        recommendations = []
        user_budget = (my_profile.budget_min, my_profile.budget_max)
        for cand, cand_user, cand_privacy in rows:
            v2 = list(cand.lifestyle_vector) if cand.lifestyle_vector is not None else []
            sim = cosine_similarity(my_vector, v2)
            breakdown_dict = compute_10_dimension_compatibility(
                user_traits=my_profile.lifestyle_traits or {},
                target_traits=cand.lifestyle_traits or {},
                user_budget=user_budget,
                target_budget=(cand.budget_min, cand.budget_max),
                user_occupation=my_profile.occupation,
                target_occupation=cand.occupation,
                user_preferred_locs=my_profile.preferred_locations or [],
                target_preferred_locs=cand.preferred_locations or [],
                vector_sim=sim,
                user_dealbreakers=dealbreakers,
            )
            rank_score = None
            if ranker is not None:
                their_bio = bios.get(cand.user_id)
                rank_score = ranker.score(pair_features(
                    breakdown_dict, vector_sim=sim,
                    bio_similarity=cosine(my_bio, their_bio) if my_bio and their_bio else None,
                    candidate_verified=bool(cand_user.is_verified),
                    candidate_has_avatar=bool(cand.avatar_url), candidate_has_bio=bool(cand.bio),
                ))
            recommendations.append(FlatmateMatchResponse(
                profile=build_profile_response(cand, cand_user, cand_privacy, requester_id=user_id),
                match_score=ScoreBreakdownSchema(**breakdown_dict),
                ranking="learned" if ranker is not None else "heuristic",
                rank_score=round(rank_score, 4) if rank_score is not None else None,
            ))

        if ranker is not None:
            recommendations.sort(key=lambda r: r.rank_score or 0.0, reverse=True)
        else:
            recommendations.sort(key=lambda r: r.match_score.overall_score, reverse=True)
        return recommendations[:limit]

    async def _bio_embeddings(self, user_ids: List[UUID]) -> Dict[UUID, List[float]]:
        """'About me' vectors from the current embedding model, keyed by user id."""
        if not user_ids:
            return {}
        rows = (await self.db.execute(
            select(ContentEmbedding.entity_id, ContentEmbedding.embedding).where(
                ContentEmbedding.entity_type == "profile",
                ContentEmbedding.model == get_embedder("profile").model_id,
                ContentEmbedding.entity_id.in_(user_ids),
            )
        )).all()
        return {r[0]: list(r[1]) for r in rows}

    async def _pair_profiles(self, user_id: UUID, target_user_id: UUID) -> Optional[Tuple[Profile, Profile, bool]]:
        """Both profiles and whether the candidate is verified, in one query (None if either is missing)."""
        rows = (await self.db.execute(
            select(Profile, User.is_verified)
            .join(User, User.id == Profile.user_id)
            .where(Profile.user_id.in_([user_id, target_user_id]))
        )).all()
        found = {profile.user_id: (profile, verified) for profile, verified in rows}
        mine, theirs = found.get(user_id), found.get(target_user_id)
        if not mine or not theirs:
            return None
        return mine[0], theirs[0], bool(theirs[1])

    async def _pair_scores(self, user_id: UUID, target_user_id: UUID) -> Optional[Tuple[dict, Dict[str, float]]]:
        """The compatibility breakdown and the ranking features for one pair, or None if a profile is missing."""
        pair = await self._pair_profiles(user_id, target_user_id)
        if pair is None:
            return None
        p1, p2, candidate_verified = pair
        breakdown = await self._breakdown(user_id, p1, p2)
        bios = await self._bio_embeddings([user_id, target_user_id])
        mine, theirs = bios.get(user_id), bios.get(target_user_id)
        v1 = list(p1.lifestyle_vector) if p1.lifestyle_vector is not None else []
        v2 = list(p2.lifestyle_vector) if p2.lifestyle_vector is not None else []
        features = pair_features(
            breakdown, vector_sim=cosine_similarity(v1, v2),
            bio_similarity=cosine(mine, theirs) if mine and theirs else None,
            candidate_verified=candidate_verified,
            candidate_has_avatar=bool(p2.avatar_url), candidate_has_bio=bool(p2.bio),
        )
        return breakdown, features

    async def pair_features(self, user_id: UUID, target_user_id: UUID) -> Optional[Dict[str, float]]:
        """Ranking features for one (viewer, candidate) pair, or None if a profile is missing."""
        scores = await self._pair_scores(user_id, target_user_id)
        return scores[1] if scores else None

    async def get_pairwise_score(self, user_id: UUID, target_user_id: UUID) -> ScoreBreakdownSchema:
        pair = await self._pair_profiles(user_id, target_user_id)
        if pair is None:
            raise NotFoundException("One or both profiles could not be found")
        p1, p2, _ = pair
        return ScoreBreakdownSchema(**(await self._breakdown(user_id, p1, p2)))

    async def _breakdown(self, user_id: UUID, p1: Profile, p2: Profile) -> dict:
        db_query = select(UserDealbreaker).where(UserDealbreaker.user_id == user_id)
        dbs_res = await self.db.execute(db_query)
        dealbreakers = [{"rule_key": d.rule_key, "is_strict": d.is_strict, "expected_value": d.expected_value} for d in dbs_res.scalars().all()]

        v1 = list(p1.lifestyle_vector) if p1.lifestyle_vector is not None else []
        v2 = list(p2.lifestyle_vector) if p2.lifestyle_vector is not None else []
        sim = cosine_similarity(v1, v2)

        breakdown = compute_10_dimension_compatibility(
            user_traits=p1.lifestyle_traits or {},
            target_traits=p2.lifestyle_traits or {},
            user_budget=(p1.budget_min, p1.budget_max),
            target_budget=(p2.budget_min, p2.budget_max),
            user_occupation=p1.occupation,
            target_occupation=p2.occupation,
            user_preferred_locs=p1.preferred_locations or [],
            target_preferred_locs=p2.preferred_locations or [],
            vector_sim=sim,
            user_dealbreakers=dealbreakers,
        )
        return breakdown

    async def record_interaction(
        self,
        user_id: UUID,
        target_user_id: UUID,
        action: str
    ) -> MatchInteractionResponse:
        if action not in VALID_INTERACTION_ACTIONS:
            raise BadRequestException(f"Invalid interaction action: {action}")
        if user_id == target_user_id:
            raise BadRequestException("Cannot record an interaction with yourself")

        # Moderation check: cannot interact with blocked user
        block_check = select(UserBlock).where(
            or_(
                and_(UserBlock.user_id == user_id, UserBlock.blocked_user_id == target_user_id),
                and_(UserBlock.user_id == target_user_id, UserBlock.blocked_user_id == user_id),
            )
        )
        if (await self.db.execute(block_check)).scalar_one_or_none():
            raise ForbiddenException("Cannot interact with a blocked user")

        # 1. My earlier decision about them and theirs about me, in one query.
        pair_rows = (await self.db.execute(select(MatchInteraction).where(or_(
            and_(MatchInteraction.user_id == user_id, MatchInteraction.target_user_id == target_user_id),
            and_(MatchInteraction.user_id == target_user_id, MatchInteraction.target_user_id == user_id),
        )))).scalars().all()
        interaction = next((r for r in pair_rows if r.user_id == user_id), None)
        reciprocal = next((r for r in pair_rows if r.user_id == target_user_id
                           and r.action in ("like", "super_like")), None)

        # Free tier: a daily cap on new likes (re-liking someone already liked doesn't count).
        is_new_like = action in ("like", "super_like") and not (interaction and interaction.action in ("like", "super_like"))
        if is_new_like:
            await ensure_can_like(self.db, user_id)

        # Snapshot what the user saw when they decided: training data for the learned ranker.
        try:
            scores = await self._pair_scores(user_id, target_user_id)
        except Exception:
            scores = None
        features = scores[1] if scores else None
        if interaction:
            interaction.action = action
            interaction.created_at = datetime.now(timezone.utc)  # when they last decided
            interaction.features = features
        else:
            interaction = MatchInteraction(
                user_id=user_id,
                target_user_id=target_user_id,
                action=action,
                features=features,
            )
            self.db.add(interaction)
        await self.db.flush()

        is_mutual = False
        mutual_id: Optional[UUID] = None
        comp_score: Optional[float] = None

        # 2. Check for mutual match
        if action in ("like", "super_like"):
            if reciprocal:
                is_mutual = True
                # Canonical pair ordering (min, max) to prevent duplicate reverse records
                u1 = min(user_id, target_user_id)
                u2 = max(user_id, target_user_id)

                match_q = select(MutualMatch).where(
                    MutualMatch.user_one_id == u1,
                    MutualMatch.user_two_id == u2
                )
                existing_match = (await self.db.execute(match_q)).scalar_one_or_none()

                # The score was already worked out for the features above; reuse it.
                breakdown = (ScoreBreakdownSchema(**scores[0]) if scores
                             else await self.get_pairwise_score(user_id, target_user_id))
                comp_score = breakdown.overall_score

                if existing_match:
                    existing_match.status = "matched"
                    existing_match.compatibility_score = comp_score
                    existing_match.score_breakdown = breakdown.model_dump()
                    mutual_id = existing_match.id
                else:
                    new_match = MutualMatch(
                        user_one_id=u1,
                        user_two_id=u2,
                        compatibility_score=comp_score,
                        algorithm_version=ALGORITHM_VERSION,
                        score_breakdown=breakdown.model_dump(),
                        status="matched"
                    )
                    self.db.add(new_match)
                    await self.db.flush()
                    mutual_id = new_match.id

        await self.db.commit()
        interaction_id = interaction.id
        if is_mutual:
            await notification_events.match_created(self.db, user_id, target_user_id, mutual_id)
        elif is_new_like:
            await notification_events.like_received(self.db, target_user_id, super_like=action == "super_like")
        return MatchInteractionResponse(
            interaction_id=interaction_id or uuid4(),
            user_id=user_id,
            target_user_id=target_user_id,
            action=action,
            is_mutual_match=is_mutual,
            mutual_match_id=mutual_id,
            compatibility_score=comp_score,
        )

    async def likes_received(self, user_id: UUID, limit: int = 50) -> Dict[str, object]:
        """People who liked me and whom I haven't answered yet (not blocked either way).

        Everyone sees how many; Seeker Pro sees who. Only people with public profiles are named:
        "matched only" and private profiles stay hidden until there is a match.
        """
        answered = select(MatchInteraction.target_user_id).where(MatchInteraction.user_id == user_id)
        blocked = select(UserBlock.blocked_user_id).where(UserBlock.user_id == user_id)
        blockers = select(UserBlock.user_id).where(UserBlock.blocked_user_id == user_id)
        base = (
            select(MatchInteraction)
            .join(User, User.id == MatchInteraction.user_id)
            .where(
                MatchInteraction.target_user_id == user_id,
                MatchInteraction.action.in_(("like", "super_like")),
                MatchInteraction.user_id.not_in(answered),
                MatchInteraction.user_id.not_in(blocked),
                MatchInteraction.user_id.not_in(blockers),
                User.is_active.is_(True),
            )
        )
        total = int(await self.db.scalar(select(func.count()).select_from(base.subquery())) or 0)
        ent = await get_entitlements(self.db, user_id)
        if not ent.who_liked_me or total == 0:
            return {"count": total, "locked": not ent.who_liked_me, "people": [], "hidden": total,
                    "upgrade_available": ent.billing_enabled and not ent.who_liked_me}

        visibility = func.coalesce(UserPrivacySetting.profile_visibility, "public")
        rows = (await self.db.execute(
            base.add_columns(User.full_name, Profile.display_name, Profile.avatar_url, Profile.occupation)
            .outerjoin(Profile, Profile.user_id == MatchInteraction.user_id)
            .outerjoin(UserPrivacySetting, UserPrivacySetting.user_id == MatchInteraction.user_id)
            .where(visibility == "public")
            .order_by(MatchInteraction.created_at.desc())
            .limit(limit)
        )).all()
        people = [
            {
                "user_id": it.user_id, "name": display or full_name or "Flatmate member",
                "avatar_url": avatar, "occupation": occupation,
                "super_like": it.action == "super_like", "liked_at": it.created_at,
            }
            for it, full_name, display, avatar, occupation in rows
        ]
        return {"count": total, "locked": False, "people": people, "hidden": max(0, total - len(people)),
                "upgrade_available": False}

    async def get_mutual_matches(self, user_id: UUID) -> List[MutualMatchItemResponse]:
        query = select(MutualMatch).where(
            or_(MutualMatch.user_one_id == user_id, MutualMatch.user_two_id == user_id),
            MutualMatch.status == "matched"
        ).order_by(MutualMatch.matched_at.desc())
        matches = (await self.db.execute(query)).scalars().all()

        results = []
        for m in matches:
            partner_id = m.user_two_id if m.user_one_id == user_id else m.user_one_id
            user_q = select(User).where(User.id == partner_id)
            user_rec = (await self.db.execute(user_q)).scalar_one_or_none()

            prof_q = select(Profile).where(Profile.user_id == partner_id)
            prof_rec = (await self.db.execute(prof_q)).scalar_one_or_none()

            results.append(MutualMatchItemResponse(
                id=m.id,
                partner_id=partner_id,
                partner_name=user_rec.full_name if user_rec else "Flatmate Seeker",
                partner_avatar=prof_rec.avatar_url if prof_rec else None,
                partner_occupation=prof_rec.occupation if prof_rec else None,
                compatibility_score=m.compatibility_score,
                algorithm_version=m.algorithm_version,
                score_breakdown=m.score_breakdown,
                status=m.status,
            ))
        return results
