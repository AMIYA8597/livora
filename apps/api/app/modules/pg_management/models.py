"""
Paying Guest (PG) & Hostel Accommodation Domain Models
Manages PG buildings, floor wings, bed-level allocations, meal arrangements, and rules.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class PGBuilding(Base):
    __tablename__ = "pg_buildings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    building_name: Mapped[str] = mapped_column(String(150), nullable=False) # e.g. "Stanza Living - Poznan House"
    pg_type: Mapped[str] = mapped_column(String(32), default="coed", nullable=False) # gents, ladies, coed
    total_floors: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    
    # Meals & Food
    food_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(50), default="veg_and_non_veg", nullable=False) # pure_veg, veg_and_non_veg
    meals_served_per_day: Mapped[int] = mapped_column(Integer, default=3, nullable=False) # Breakfast, Lunch, Dinner
    
    # House Rules
    gate_closing_time: Mapped[Optional[str]] = mapped_column(String(10), default="22:30", nullable=True) # "22:30"
    notice_period_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    biometric_entry: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    operator = relationship("User", foreign_keys=[operator_id])
    property = relationship("Property")
    floors: Mapped[List["PGFloor"]] = relationship("PGFloor", back_populates="pg_building", cascade="all, delete-orphan")

class PGFloor(Base):
    __tablename__ = "pg_floors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pg_building_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pg_buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number: Mapped[int] = mapped_column(Integer, nullable=False) # 1, 2, 3
    gender_restriction: Mapped[str] = mapped_column(String(32), default="coed", nullable=False) # female_only, male_only, coed
    total_rooms: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    pg_building: Mapped["PGBuilding"] = relationship("PGBuilding", back_populates="floors")
