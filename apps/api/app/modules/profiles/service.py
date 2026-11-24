from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.modules.profiles.models import Profile
from app.modules.users.models import User, UserPrivacySetting
from app.modules.matching.models import MutualMatch
from app.modules.profiles.schemas import ProfileUpdate, LifestyleTraitsSchema, PrivacySettingsUpdate, ProfileResponse
from app.core.exceptions import NotFoundException, ForbiddenException
from app.core.config import settings
from app.ml.indexing import queue_embedding_refresh
from app.modules.lifestyle.traits import canonical_traits, lifestyle_vector

def compute_lifestyle_vector(traits: LifestyleTraitsSchema) -> list:
    """The matching vector for quiz answers (old values converted to the form's vocabulary)."""
    return lifestyle_vector(traits.model_dump(), settings.VECTOR_EMBEDDING_DIM)

def build_profile_response(
    profile: Profile,
    user: User,
    privacy: Optional[UserPrivacySetting],
    requester_id: UUID,
    is_admin: bool = False,
) -> ProfileResponse:
    """Serialise a profile for a requester, applying phone masking. Access checks are the caller's job."""
    show_phone_publicly = bool(privacy and privacy.show_phone_publicly)
    # Mask phone number if required
    phone_to_expose = None
    if requester_id == profile.user_id or is_admin or show_phone_publicly:
        phone_to_expose = user.phone_number
    elif user.phone_number:
        if len(user.phone_number) >= 8:
            phone_to_expose = f"{user.phone_number[:3]}******{user.phone_number[-2:]}"
        else:
            phone_to_expose = "******"

    response_dict = {
        "id": profile.id,
        "user_id": profile.user_id,
        "is_verified": bool(user.is_verified),
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
        if {"bio", "occupation", "preferred_locations"} & update_dict.keys():
            queue_embedding_refresh(self.db, "profile", user_id)

        await self.db.commit()
        await self.db.refresh(profile)
        return profile

    update_profile = update

    async def submit_lifestyle_quiz(self, user_id: UUID, quiz: LifestyleTraitsSchema) -> Profile:
        profile = await self.get_by_user_id(user_id)
        if not profile:
            raise NotFoundException("Profile not found")

        # Merged into the existing copy, so answers only the 10-dimension form has are kept.
        traits = canonical_traits({**(profile.lifestyle_traits or {}), **canonical_traits(quiz.model_dump())})
        profile.lifestyle_traits = traits
        profile.lifestyle_vector = lifestyle_vector(traits, settings.VECTOR_EMBEDDING_DIM)
        queue_embedding_refresh(self.db, "profile", user_id)

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

        return build_profile_response(profile, user, privacy, requester_id, is_admin)
