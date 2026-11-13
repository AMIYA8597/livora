"""
Paying Guest (PG) & Hostel Management Schemas
"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class PGFloorCreate(BaseModel):
    floor_number: int = Field(..., ge=0, description="Floor level, 0 for Ground")
    gender_restriction: str = Field(default="coed", description="female_only, male_only, coed")
    total_rooms: int = Field(default=4, ge=1)

class PGFloorResponse(BaseModel):
    id: uuid.UUID
    pg_building_id: uuid.UUID
    floor_number: int
    gender_restriction: str
    total_rooms: int
    model_config = ConfigDict(from_attributes=True)

class PGBuildingCreate(BaseModel):
    property_id: uuid.UUID
    building_name: str = Field(..., description="e.g. Stanza Living - Poznan House")
    pg_type: str = Field(default="coed", description="gents, ladies, coed")
    total_floors: int = Field(default=3, ge=1)
    food_included: bool = True
    meal_type: str = Field(default="veg_and_non_veg", description="pure_veg, veg_and_non_veg")
    meals_served_per_day: int = Field(default=3, ge=1, le=4)
    gate_closing_time: Optional[str] = Field(default="22:30", description="HH:MM curfew time")
    notice_period_days: int = Field(default=30, ge=0)
    biometric_entry: bool = True
    floors: Optional[List[PGFloorCreate]] = []

class PGBuildingResponse(BaseModel):
    id: uuid.UUID
    operator_id: uuid.UUID
    property_id: uuid.UUID
    building_name: str
    pg_type: str
    total_floors: int
    food_included: bool
    meal_type: str
    meals_served_per_day: int
    gate_closing_time: Optional[str]
    notice_period_days: int
    biometric_entry: bool
    created_at: datetime
    floors: List[PGFloorResponse] = []
    model_config = ConfigDict(from_attributes=True)
