"""
Lifestyle Taxonomy & Granular Preferences Schemas
10-Dimension Compatibility Questionnaire and Dealbreakers
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class LifestylePreferencesBase(BaseModel):
    # 1. Sleep & Daily Schedule
    sleep_schedule: str = Field(default="flexible", description="early_bird, night_owl, flexible, rotational")
    wake_time_typical: Optional[str] = Field(default="07:00", description="HH:MM format")
    sleep_time_typical: Optional[str] = Field(default="23:00", description="HH:MM format")

    # 2. Work & Occupation Schedule
    work_arrangement: str = Field(default="hybrid", description="remote, hybrid, on_site, shift_work")

    # 3. Cleanliness & Household Chores
    cleanliness_level: int = Field(default=3, ge=1, le=5, description="1 (Relaxed) to 5 (Meticulous)")
    chore_philosophy: str = Field(default="shared_roster", description="cook_maid, shared_roster, self_service")

    # 4. Noise & Environment Tolerance
    noise_tolerance: str = Field(default="moderate", description="quiet_library, moderate, lively")
    instrument_or_music: bool = Field(default=False, description="Plays musical instruments or loud audio")

    # 5. Lighting & Bedroom Darkness
    lighting_preference: str = Field(default="dim", description="pitch_black, dim, flexible")

    # 6. Guests & Social Vibe
    guests_policy: str = Field(default="occasional_weekends", description="rarely, advance_notice, occasional_weekends, open_house")
    social_battery: str = Field(default="balanced", description="introverted, balanced, extroverted")

    # 7. Dietary & Cooking Habits (India Specific)
    diet_preference: str = Field(default="omnivore", description="pure_veg, eggetarian, non_veg, vegan, jain")
    non_veg_cooking_allowed: bool = Field(default=True, description="Whether non-veg cooking is allowed in the kitchen")
    cooks_at_home: str = Field(default="sometimes", description="daily, sometimes, hires_cook, orders_online")

    # 8. Substance & Habits
    smoking: str = Field(default="never", description="never, outside_only, permitted")
    drinking: str = Field(default="socially", description="teetotaler, socially, regular")

    # 9. Pets Policy & Allergies
    pet_preference: str = Field(default="cats_and_dogs_ok", description="no_pets, loves_pets, cats_ok, dogs_ok, allergic")

    # 10. Notes
    custom_notes: Optional[str] = Field(default=None, description="Free text context on habits or roommate expectations")

class LifestyleCreateOrUpdate(LifestylePreferencesBase):
    pass

class LifestyleResponse(LifestylePreferencesBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DealbreakerCreate(BaseModel):
    rule_key: str = Field(..., description="e.g. no_smoking_inside, pure_veg_kitchen_only, no_opposite_gender_overnight, no_pets_allowed, quiet_after_11pm")
    is_strict: bool = Field(default=True, description="Strict dealbreaker completely zeroes out compatibility score if violated")
    expected_value: str = Field(..., description="Expected value constraint, e.g. 'never', 'pure_veg', 'quiet_library'")

class DealbreakerResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    rule_key: str
    is_strict: bool
    expected_value: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
