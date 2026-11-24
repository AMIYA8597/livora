import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class LifestyleTraitsSchema(BaseModel):
    sleep_schedule: str = "early_bird"        # early_bird, night_owl, flexible
    cleanliness_level: int = 4                # 1 to 5
    social_battery: str = "moderate"          # introverted, moderate, extroverted, balanced
    work_arrangement: str = "hybrid"          # remote, hybrid, on_site
    diet: str = "omnivore"                    # omnivore, vegetarian, vegan, pescatarian, halal, kosher
    smoking: str = "never"                    # never, outside_only, allowed
    pets: str = "cats_ok"                     # loves_pets, has_cat, has_dog, cats_ok, dogs_ok, no_pets
    guests_policy: str = "occasional_weekends"

class ProfileBase(BaseModel):
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    education_institute: Optional[str] = None
    education_degree: Optional[str] = None
    company_name: Optional[str] = None
    designation: Optional[str] = None
    budget_min: int = 500
    budget_max: int = 2500
    move_in_date: Optional[date] = None
    lease_duration_months: int = 12
    preferred_locations: List[str] = []

class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    education_institute: Optional[str] = None
    education_degree: Optional[str] = None
    company_name: Optional[str] = None
    designation: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    move_in_date: Optional[date] = None
    lease_duration_months: Optional[int] = None
    preferred_locations: Optional[List[str]] = None

class ProfileResponse(ProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID
    # Has a verified work or college email (users.is_verified).
    is_verified: bool = False
    phone_number: Optional[str] = None
    lifestyle_traits: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PrivacySettingsUpdate(BaseModel):
    show_phone_publicly: Optional[bool] = None
    show_exact_location: Optional[bool] = None
    allow_direct_messages: Optional[bool] = None
    profile_visibility: Optional[str] = Field(default=None, description="public, matched_only, private")

class PrivacySettingsResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    show_phone_publicly: bool
    show_exact_location: bool
    allow_direct_messages: bool
    profile_visibility: str
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
