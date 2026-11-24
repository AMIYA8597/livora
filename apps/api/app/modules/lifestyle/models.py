"""
Lifestyle Taxonomy & Granular Preferences Domain Models
Normalized representation of 10-dimension compatibility attributes and dealbreakers.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class LifestyleProfile(Base):
    __tablename__ = "lifestyle_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # 1. Sleep & Daily Schedule
    sleep_schedule: Mapped[str] = mapped_column(String(32), default="flexible", nullable=False) # early_bird, night_owl, flexible, rotational
    wake_time_typical: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # "06:30"
    sleep_time_typical: Mapped[Optional[str]] = mapped_column(String(10), nullable=True) # "23:00"

    # 2. Work & Occupation Schedule
    work_arrangement: Mapped[str] = mapped_column(String(32), default="hybrid", nullable=False) # remote, hybrid, on_site, shift_work

    # 3. Cleanliness & Household Chores
    cleanliness_level: Mapped[int] = mapped_column(Integer, default=3, nullable=False) # 1 (Relaxed) to 5 (Meticulous)
    chore_philosophy: Mapped[str] = mapped_column(String(50), default="shared_roster", nullable=False) # cook_maid, shared_roster, self_service

    # 4. Noise & Environment Tolerance
    noise_tolerance: Mapped[str] = mapped_column(String(32), default="moderate", nullable=False) # quiet_library, moderate, lively
    instrument_or_music: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 5. Lighting & Bedroom Darkness
    lighting_preference: Mapped[str] = mapped_column(String(32), default="dim", nullable=False) # pitch_black, night_light, flexible

    # 6. Guests & Social Vibe
    guests_policy: Mapped[str] = mapped_column(String(50), default="occasional_weekends", nullable=False) # rarely, advance_notice, occasional_weekends, open_house
    social_battery: Mapped[str] = mapped_column(String(32), default="balanced", nullable=False) # introverted, balanced, extroverted

    # 7. Dietary & Cooking Habits (Crucial in Indian flatshares)
    diet_preference: Mapped[str] = mapped_column(String(32), default="non_veg", nullable=False) # pure_veg, jain, eggetarian, non_veg, vegan
    non_veg_cooking_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cooks_at_home: Mapped[str] = mapped_column(String(32), default="sometimes", nullable=False) # daily, sometimes, hires_cook, orders_online

    # 8. Substance & Habits
    smoking: Mapped[str] = mapped_column(String(32), default="never", nullable=False) # never, outside_only, permitted
    drinking: Mapped[str] = mapped_column(String(32), default="socially", nullable=False) # teetotaler, socially, regular

    # 9. Pets Policy & Allergies
    pet_preference: Mapped[str] = mapped_column(String(32), default="cats_and_dogs_ok", nullable=False) # no_pets, loves_pets, cats_ok, dogs_ok, allergic

    # 10. Vector Representation for ANN Similarity Search
    preference_vector: Mapped[list] = mapped_column(ARRAY(Float), default=list, nullable=False)
    custom_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

class UserDealbreaker(Base):
    __tablename__ = "user_dealbreakers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "no_smoking_inside", "pure_veg_kitchen_only", "no_opposite_gender_overnight"
    is_strict: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expected_value: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User")
