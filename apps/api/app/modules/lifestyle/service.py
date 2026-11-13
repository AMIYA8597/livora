"""
Lifestyle Service
Handles 10-dimension questionnaire submission, 64-dim vector embedding, and dealbreakers.
"""
from typing import Optional, List
from uuid import UUID
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.lifestyle.models import LifestyleProfile, UserDealbreaker
from app.modules.lifestyle.schemas import LifestylePreferencesBase, LifestyleCreateOrUpdate, DealbreakerCreate
from app.core.exceptions import NotFoundException
from app.core.config import settings

def compute_lifestyle_profile_vector(traits: LifestylePreferencesBase) -> list[float]:
    """
    Computes a 64-dimensional normalized vector from the 10 lifestyle dimensions
    to support cosine similarity (<=>) in PostGIS/pgvector.
    """
    dim = settings.VECTOR_EMBEDDING_DIM
    vec = [0.0] * dim

    # Dimension 1: Sleep Schedule (0-7)
    sleep_map = {"early_bird": 1.0, "flexible": 0.6, "rotational": 0.4, "night_owl": 0.1}
    s_val = sleep_map.get(traits.sleep_schedule, 0.5)
    for i in range(0, 8):
        vec[i] = s_val * math.cos(i * 0.785)

    # Dimension 2: Work Arrangement (8-15)
    work_map = {"remote": 0.1, "hybrid": 0.5, "on_site": 0.8, "shift_work": 1.0}
    w_val = work_map.get(traits.work_arrangement, 0.5)
    for i in range(8, 16):
        vec[i] = w_val * math.sin(i * 0.785)

    # Dimension 3: Cleanliness Level & Chores (16-23)
    clean_val = traits.cleanliness_level / 5.0
    for i in range(16, 24):
        vec[i] = clean_val * math.cos(i * 0.5)

    # Dimension 4: Noise Tolerance & Music (24-31)
    noise_map = {"quiet_library": 0.2, "moderate": 0.6, "lively": 1.0}
    n_val = noise_map.get(traits.noise_tolerance, 0.5)
    if traits.instrument_or_music:
        n_val = min(1.0, n_val + 0.2)
    for i in range(24, 32):
        vec[i] = n_val * math.sin(i * 0.5)

    # Dimension 5: Lighting Preference (32-37)
    light_map = {"pitch_black": 0.1, "dim": 0.5, "flexible": 0.9}
    l_val = light_map.get(traits.lighting_preference, 0.5)
    for i in range(32, 38):
        vec[i] = l_val * math.cos(i * 0.6)

    # Dimension 6: Guests & Social Battery (38-43)
    social_map = {"introverted": 0.2, "balanced": 0.6, "extroverted": 1.0}
    soc_val = social_map.get(traits.social_battery, 0.5)
    for i in range(38, 44):
        vec[i] = soc_val * math.sin(i * 0.6)

    # Dimension 7: Diet & Non-Veg Cooking (44-51)
    diet_map = {"pure_veg": 0.1, "jain": 0.0, "eggetarian": 0.4, "non_veg": 0.8, "vegan": 0.2}
    d_val = diet_map.get(traits.diet_preference, 0.5)
    if not traits.non_veg_cooking_allowed:
        d_val = min(0.3, d_val)
    for i in range(44, 52):
        vec[i] = d_val * math.cos(i * 0.4)

    # Dimension 8: Smoking & Drinking (52-57)
    smk_map = {"never": 0.0, "outside_only": 0.5, "permitted": 1.0}
    smk_val = smk_map.get(traits.smoking, 0.0)
    for i in range(52, 58):
        vec[i] = smk_val * math.sin(i * 0.4)

    # Dimension 9: Pet Preference (58-63)
    pet_map = {"no_pets": 0.0, "allergic": 0.1, "cats_ok": 0.5, "dogs_ok": 0.6, "cats_and_dogs_ok": 0.8, "loves_pets": 1.0}
    p_val = pet_map.get(traits.pet_preference, 0.5)
    for i in range(58, 64):
        vec[i] = p_val * math.cos(i * 0.3)

    # Normalize vector to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

class LifestyleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Optional[LifestyleProfile]:
        query = select(LifestyleProfile).where(LifestyleProfile.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def upsert_lifestyle(self, user_id: UUID, data: LifestyleCreateOrUpdate) -> LifestyleProfile:
        profile = await self.get_by_user_id(user_id)
        vector = compute_lifestyle_profile_vector(data)
        data_dict = data.model_dump()

        if profile:
            for key, val in data_dict.items():
                setattr(profile, key, val)
            profile.preference_vector = vector
        else:
            profile = LifestyleProfile(
                user_id=user_id,
                preference_vector=vector,
                **data_dict
            )
            self.db.add(profile)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def get_dealbreakers(self, user_id: UUID) -> List[UserDealbreaker]:
        query = select(UserDealbreaker).where(UserDealbreaker.user_id == user_id).order_by(UserDealbreaker.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_dealbreaker(self, user_id: UUID, data: DealbreakerCreate) -> UserDealbreaker:
        dealbreaker = UserDealbreaker(
            user_id=user_id,
            rule_key=data.rule_key,
            is_strict=data.is_strict,
            expected_value=data.expected_value,
        )
        self.db.add(dealbreaker)
        await self.db.commit()
        await self.db.refresh(dealbreaker)
        return dealbreaker

    async def delete_dealbreaker(self, user_id: UUID, dealbreaker_id: UUID) -> bool:
        query = select(UserDealbreaker).where(
            UserDealbreaker.id == dealbreaker_id,
            UserDealbreaker.user_id == user_id
        )
        result = await self.db.execute(query)
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundException("Dealbreaker not found or access denied")

        await self.db.delete(item)
        await self.db.commit()
        return True
