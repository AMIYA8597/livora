from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
import math
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting
from app.modules.matching.models import MutualMatch
from app.modules.profiles.schemas import ProfileUpdate, LifestyleTraitsSchema, PrivacySettingsUpdate, ProfileResponse
from app.core.exceptions import NotFoundException, ForbiddenException
from app.core.config import settings

def compute_lifestyle_vector(traits: LifestyleTraitsSchema) -> list:
    """
    Encodes lifestyle traits into a normalized 64-dimensional vector
    suitable for pgvector cosine distance operations (<=>).
    """
    dim = settings.VECTOR_EMBEDDING_DIM
    vec = [0.0] * dim

    # Dimension slices:
    # 0-7: Sleep schedule
    sleep_map = {"early_bird": 1.0, "flexible": 0.5, "night_owl": 0.0}
    val = sleep_map.get(traits.sleep_schedule, 0.5)
    for i in range(0, 8):
        vec[i] = val * math.cos(i)

    # 8-15: Cleanliness level (scale 1-5 normalized to 0.2 - 1.0)
    clean_val = traits.cleanliness_level / 5.0
    for i in range(8, 16):
        vec[i] = clean_val * math.sin(i)

    # 16-23: Social battery
    soc_map = {"introverted": 0.2, "moderate": 0.5, "balanced": 0.7, "extroverted": 1.0}
    soc_val = soc_map.get(traits.social_battery, 0.5)
    for i in range(16, 24):
        vec[i] = soc_val * math.cos(i)

    # 24-31: Work arrangement
    work_map = {"remote": 0.1, "hybrid": 0.5, "on_site": 0.9}
    work_val = work_map.get(traits.work_arrangement, 0.5)
    for i in range(24, 32):
        vec[i] = work_val * math.sin(i)

    # 32-39: Diet
    diet_map = {"vegan": 1.0, "vegetarian": 0.8, "pescatarian": 0.6, "omnivore": 0.4}
    diet_val = diet_map.get(traits.diet, 0.5)
    for i in range(32, 40):
        vec[i] = diet_val * math.cos(i)

    # 40-47: Smoking
    smk_map = {"never": 0.0, "outside_only": 0.5, "allowed": 1.0}
    smk_val = smk_map.get(traits.smoking, 0.0)
    for i in range(40, 48):
        vec[i] = smk_val * math.sin(i)

    # 48-63: Pets and general vibe
    pet_map = {"no_pets": 0.0, "cats_ok": 0.4, "dogs_ok": 0.6, "loves_pets": 1.0}
    pet_val = pet_map.get(traits.pets, 0.5)
    for i in range(48, 64):
        vec[i] = pet_val * math.cos(i * 0.5)

    # L2 Normalization
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user_id(self, user_id: UUID) -> Optional[Profile]:
        query = select(Profile).where(Profile.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_privacy_settings(self, user_id: UUID) -> UserPrivacySetting:
        query = select(UserPrivacySetting).where(UserPrivacySetting.user_id == user_id)
        result = await self.db.execute(query)
        settings_rec = result.scalar_one_or_none()
        if not settings_rec:
            # Create default privacy settings
            settings_rec = UserPrivacySetting(
                user_id=user_id,
                show_phone_publicly=False,
                show_exact_location=False,
                allow_direct_messages=True,
                profile_visibility="public"
            )
            self.db.add(settings_rec)
            await self.db.commit()
            await self.db.refresh(settings_rec)
        return settings_rec

    async def update_privacy_settings(self, user_id: UUID, data: PrivacySettingsUpdate) -> UserPrivacySetting:
        settings_rec = await self.get_privacy_settings(user_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            if val is not None:
                setattr(settings_rec, key, val)
        await self.db.commit()
        await self.db.refresh(settings_rec)
        return settings_rec

    async def update(self, user_id: UUID, data: ProfileUpdate) -> Profile:
        profile = await self.get_by_user_id(user_id)
        if not profile:
            raise NotFoundException("Profile not found")

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(profile, key, value)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    update_profile = update

    async def submit_lifestyle_quiz(self, user_id: UUID, quiz: LifestyleTraitsSchema) -> Profile:
        profile = await self.get_by_user_id(user_id)
        if not profile:
            raise NotFoundException("Profile not found")

        profile.lifestyle_traits = quiz.model_dump()
        profile.lifestyle_vector = compute_lifestyle_vector(quiz)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    async def get_profile_with_privacy(self, requester_id: UUID, target_user_id: UUID, is_admin: bool = False) -> ProfileResponse:
        profile = await self.get_by_user_id(target_user_id)
        if not profile:
            raise NotFoundException("Profile not found")

        user_query = select(User).where(User.id == target_user_id)
        user_res = await self.db.execute(user_query)
        user = user_res.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")

        privacy = await self.get_privacy_settings(target_user_id)

        # Enforce visibility rules if not self and not admin
        if requester_id != target_user_id and not is_admin:
            if privacy.profile_visibility == "private":
                raise ForbiddenException("This profile is private")
            elif privacy.profile_visibility == "matched_only":
                match_query = select(MutualMatch).where(
                    or_(
                        and_(MutualMatch.user_one_id == requester_id, MutualMatch.user_two_id == target_user_id),
                        and_(MutualMatch.user_one_id == target_user_id, MutualMatch.user_two_id == requester_id)
                    ),
                    MutualMatch.status == "matched"
                )
                match_res = await self.db.execute(match_query)
                if not match_res.scalar_one_or_none():
                    raise ForbiddenException("This profile is only visible to mutual matches")

        # Mask phone number if required
        phone_to_expose = None
        if requester_id == target_user_id or is_admin or privacy.show_phone_publicly:
            phone_to_expose = user.phone_number
        elif user.phone_number:
            if len(user.phone_number) >= 8:
                phone_to_expose = f"{user.phone_number[:3]}******{user.phone_number[-2:]}"
            else:
                phone_to_expose = "******"

        response_dict = {
            "id": profile.id,
            "user_id": profile.user_id,
            "display_name": profile.display_name,
            "avatar_url": profile.avatar_url,
            "bio": profile.bio,
            "birth_date": profile.birth_date,
            "gender": profile.gender,
            "occupation": profile.occupation,
            "education_institute": profile.education_institute,
            "education_degree": profile.education_degree,
            "company_name": profile.company_name,
            "designation": profile.designation,
            "budget_min": profile.budget_min or 500,
            "budget_max": profile.budget_max or 2500,
            "move_in_date": profile.move_in_date,
            "lease_duration_months": profile.lease_duration_months or 12,
            "preferred_locations": profile.preferred_locations or [],
            "lifestyle_traits": profile.lifestyle_traits or {},
            "phone_number": phone_to_expose,
            "created_at": profile.created_at or datetime.now(timezone.utc),
            "updated_at": profile.updated_at or datetime.now(timezone.utc),
        }
        return ProfileResponse.model_validate(response_dict)
