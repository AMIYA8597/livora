from datetime import date
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Integer, and_, func, or_, select
from app.ml.search import clean_query, rank_profiles
from app.modules.locations.models import City, Locality
from app.modules.matching.models import MutualMatch
from app.modules.moderation.models import UserBlock
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting
from app.modules.flatmates.schemas import FlatmateSearchFilter, FlatmateSeekerCard

class FlatmateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _calc_age(self, birth_date: date | None) -> int | None:
        if not birth_date:
            return None
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    async def search_flatmates(self, current_user_id: UUID, filters: FlatmateSearchFilter) -> List[FlatmateSeekerCard]:
        """Seekers visible to the requester, filtered in SQL (so pagination is exact).

        Respects profile visibility (private profiles never appear; "matched only" profiles
        appear to mutual matches) and blocks in either direction. With `q`, results are ordered
        by relevance of the person's "about me" (hybrid full-text + embedding search).
        """
        visibility = func.coalesce(UserPrivacySetting.profile_visibility, "public")
        is_mutual_match = (
            select(MutualMatch.id).where(
                or_(
                    and_(MutualMatch.user_one_id == current_user_id, MutualMatch.user_two_id == Profile.user_id),
                    and_(MutualMatch.user_one_id == Profile.user_id, MutualMatch.user_two_id == current_user_id),
                ),
                MutualMatch.status == "matched",
            ).exists()
        )
        blocked = select(UserBlock.blocked_user_id).where(UserBlock.user_id == current_user_id)
        blockers = select(UserBlock.user_id).where(UserBlock.blocked_user_id == current_user_id)
        traits = Profile.lifestyle_traits

        conditions = [
            User.id != current_user_id,
            User.is_active.is_(True),
            or_(visibility == "public", and_(visibility == "matched_only", is_mutual_match)),
            ~Profile.user_id.in_(blocked),
            ~Profile.user_id.in_(blockers),
        ]
        if filters.min_budget:
            conditions.append(Profile.budget_max >= filters.min_budget)
        if filters.max_budget:
            conditions.append(Profile.budget_min <= filters.max_budget)
        if filters.gender:
            conditions.append(Profile.gender == filters.gender)
        if filters.city:
            # Profiles list localities ("Koramangala"), not cities: match the city's known
            # localities, or the city name written into a preferred location.
            in_city = (
                select(Locality.id).join(City, City.id == Locality.city_id)
                .where(City.name.ilike(filters.city.strip()), Locality.name == func.any(Profile.preferred_locations))
                .exists()
            )
            conditions.append(or_(
                in_city,
                func.array_to_string(Profile.preferred_locations, " ").ilike(f"%{filters.city.strip()}%"),
            ))
        if filters.sleep_schedule:
            conditions.append(traits["sleep_schedule"].astext == filters.sleep_schedule)
        if filters.diet:
            conditions.append(traits["diet"].astext == filters.diet)
        if filters.smoking:
            conditions.append(traits["smoking"].astext == filters.smoking)
        if filters.pets:
            conditions.append(traits["pets"].astext == filters.pets)
        if filters.cleanliness_min:
            conditions.append(
                func.coalesce(traits["cleanliness_level"].astext, "0").cast(Integer) >= filters.cleanliness_min
            )

        base = (
            select(Profile, User)
            .join(User, Profile.user_id == User.id)
            .outerjoin(UserPrivacySetting, UserPrivacySetting.user_id == Profile.user_id)
            .where(*conditions)
        )

        text_query = clean_query(filters.q)
        if text_query:
            eligible = (
                select(Profile.user_id)
                .join(User, Profile.user_id == User.id)
                .outerjoin(UserPrivacySetting, UserPrivacySetting.user_id == Profile.user_id)
                .where(*conditions)
            )
            ranking = await rank_profiles(self.db, text_query, eligible)
            page_ids = ranking.ids[filters.offset:filters.offset + filters.limit]
            if not page_ids:
                return []
            rows = (await self.db.execute(base.where(Profile.user_id.in_(page_ids)))).all()
            by_id = {profile.user_id: (profile, user) for profile, user in rows}
            ordered = [by_id[i] for i in page_ids if i in by_id]
        else:
            ordered = (await self.db.execute(
                base.order_by(Profile.updated_at.desc().nullslast(), Profile.user_id)
                .limit(filters.limit).offset(filters.offset)
            )).all()

        return [
            FlatmateSeekerCard(
                user_id=user.id,
                display_name=profile.display_name,
                avatar_url=profile.avatar_url,
                bio=profile.bio,
                age=self._calc_age(profile.birth_date),
                occupation=profile.occupation,
                budget_min=profile.budget_min,
                budget_max=profile.budget_max,
                preferred_locations=profile.preferred_locations,
                lifestyle_traits=profile.lifestyle_traits or {},
                is_verified=user.is_verified,
            )
            for profile, user in ordered
        ]
