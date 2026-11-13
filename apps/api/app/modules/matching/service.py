from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.modules.profiles.models import Profile
from app.modules.users.models import User
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
from app.modules.profiles.service import ProfileService
from app.core.exceptions import NotFoundException, BadRequestException

VALID_INTERACTION_ACTIONS = {"like", "pass", "save", "super_like"}

class MatchingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_recommendations(self, user_id: UUID, limit: int = 10) -> List[FlatmateMatchResponse]:
        profile_service = ProfileService(self.db)
        my_profile = await profile_service.get_by_user_id(user_id)
        if not my_profile:
            raise NotFoundException("Your profile has not been set up yet. Please complete your profile.")

        # Load user dealbreakers
        db_query = select(UserDealbreaker).where(UserDealbreaker.user_id == user_id)
        dbs_res = await self.db.execute(db_query)
        dealbreakers = [{"rule_key": d.rule_key, "is_strict": d.is_strict, "expected_value": d.expected_value} for d in dbs_res.scalars().all()]

        # Query other candidate profiles
        candidates_query = select(Profile).where(Profile.user_id != user_id).limit(50)
        candidates = (await self.db.execute(candidates_query)).scalars().all()

        recommendations = []
        user_budget = (my_profile.budget_min, my_profile.budget_max)

        for cand in candidates:
            cand_budget = (cand.budget_min, cand.budget_max)
            v1 = list(my_profile.lifestyle_vector) if my_profile.lifestyle_vector is not None else []
            v2 = list(cand.lifestyle_vector) if cand.lifestyle_vector is not None else []
            sim = cosine_similarity(v1, v2)

            breakdown_dict = compute_10_dimension_compatibility(
                user_traits=my_profile.lifestyle_traits or {},
                target_traits=cand.lifestyle_traits or {},
                user_budget=user_budget,
                target_budget=cand_budget,
                user_occupation=my_profile.occupation,
                target_occupation=cand.occupation,
                user_preferred_locs=my_profile.preferred_locations or [],
                target_preferred_locs=cand.preferred_locations or [],
                vector_sim=sim,
                user_dealbreakers=dealbreakers,
            )

            score_schema = ScoreBreakdownSchema(**breakdown_dict)
            cand_resp = await profile_service.get_profile_with_privacy(requester_id=user_id, target_user_id=cand.user_id)
            recommendations.append(FlatmateMatchResponse(
                profile=cand_resp,
                match_score=score_schema,
            ))

        recommendations.sort(key=lambda r: r.match_score.overall_score, reverse=True)
        return recommendations[:limit]

    async def get_pairwise_score(self, user_id: UUID, target_user_id: UUID) -> ScoreBreakdownSchema:
        profile_service = ProfileService(self.db)
        p1 = await profile_service.get_by_user_id(user_id)
        p2 = await profile_service.get_by_user_id(target_user_id)

        if not p1 or not p2:
            raise NotFoundException("One or both profiles could not be found")

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
        return ScoreBreakdownSchema(**breakdown)

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

        # 1. Check or update interaction
        existing_q = select(MatchInteraction).where(
            MatchInteraction.user_id == user_id,
            MatchInteraction.target_user_id == target_user_id
        )
        existing_res = await self.db.execute(existing_q)
        interaction = existing_res.scalar_one_or_none()

        if interaction:
            interaction.action = action
        else:
            interaction = MatchInteraction(
                user_id=user_id,
                target_user_id=target_user_id,
                action=action
            )
            self.db.add(interaction)
        await self.db.flush()

        is_mutual = False
        mutual_id: Optional[UUID] = None
        comp_score: Optional[float] = None

        # 2. Check for mutual match
        if action in ("like", "super_like"):
            reciprocal_q = select(MatchInteraction).where(
                MatchInteraction.user_id == target_user_id,
                MatchInteraction.target_user_id == user_id,
                MatchInteraction.action.in_(["like", "super_like"])
            )
            reciprocal = (await self.db.execute(reciprocal_q)).scalar_one_or_none()

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

                breakdown = await self.get_pairwise_score(user_id, target_user_id)
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
        return MatchInteractionResponse(
            interaction_id=interaction.id or uuid4(),
            user_id=user_id,
            target_user_id=target_user_id,
            action=action,
            is_mutual_match=is_mutual,
            mutual_match_id=mutual_id,
            compatibility_score=comp_score,
        )

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
