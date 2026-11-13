from datetime import date
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.profiles.models import Profile
from app.modules.users.models import User
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
        query = (
            select(Profile, User)
            .join(User, Profile.user_id == User.id)
            .where(User.id != current_user_id)
            .where(User.is_active == True)
        )

        if filters.min_budget:
            query = query.where(Profile.budget_max >= filters.min_budget)
        if filters.max_budget:
            query = query.where(Profile.budget_min <= filters.max_budget)
        if filters.gender:
            query = query.where(Profile.gender == filters.gender)

        query = query.limit(filters.limit).offset(filters.offset)
        result = await self.db.execute(query)
        rows = result.all()

        cards = []
        for profile, user in rows:
            traits = profile.lifestyle_traits or {}

            # Apply JSONB filters in Python if passed
            if filters.sleep_schedule and traits.get("sleep_schedule") != filters.sleep_schedule:
                continue
            if filters.cleanliness_min and traits.get("cleanliness_level", 0) < filters.cleanliness_min:
                continue
            if filters.diet and traits.get("diet") != filters.diet:
                continue
            if filters.smoking and traits.get("smoking") != filters.smoking:
                continue

            cards.append(FlatmateSeekerCard(
                user_id=user.id,
                display_name=profile.display_name,
                avatar_url=profile.avatar_url,
                bio=profile.bio,
                age=self._calc_age(profile.birth_date),
                occupation=profile.occupation,
                budget_min=profile.budget_min,
                budget_max=profile.budget_max,
                preferred_locations=profile.preferred_locations,
                lifestyle_traits=traits,
                is_verified=user.is_verified,
            ))
        return cards
