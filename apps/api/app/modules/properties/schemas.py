"""
Comprehensive Property & Accommodation Domain Schemas
Covers Indian configurations (1RK, 1BHK, 2BHK, 3BHK, 4BHK+, PG), Rooms, Beds, and Financials.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class BedBase(BaseModel):
    bed_identifier: str = Field(..., description="e.g. Bed A, Bed 1 (Window)")
    monthly_rent: Decimal = Field(..., ge=0, description="Monthly rent in INR")
    available_from: date
    is_occupied: bool = False
    current_occupant_id: Optional[uuid.UUID] = None

class BedCreate(BedBase):
    pass

class BedResponse(BedBase):
    id: uuid.UUID
    room_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)

class RoomBase(BaseModel):
    room_name: str = Field(..., description="e.g. Master Bedroom with Attached Bath")
    room_type: str = Field(default="private", description="private, 2_sharing, 3_sharing, master_ensuite")
    room_rent: Decimal = Field(..., ge=0, description="Monthly rent in INR")
    deposit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Security deposit in INR")
    private_bath: bool = False
    attached_balcony: bool = False
    max_beds: int = Field(default=1, ge=1)
    occupied_beds: int = Field(default=0, ge=0)
    is_available: bool = True
    available_from: date

class RoomCreate(RoomBase):
    beds: Optional[List[BedCreate]] = []

class RoomResponse(RoomBase):
    id: uuid.UUID
    property_id: uuid.UUID
    beds: List[BedResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PropertyBase(BaseModel):
    title: str
    description: str
    property_category: str = Field(default="apartment", description="apartment, independent_house, pg, hostel, co_living, villa")
    configuration: str = Field(default="2BHK", description="1RK, 1BHK, 2RK, 2BHK, 3BHK, 4BHK_plus, studio")
    latitude: float
    longitude: float
    address_display: str = Field(..., description="Public locality name, e.g. 'HSR Layout Sector 2, Bengaluru'")
    address_exact: str = Field(..., description="Exact building/flat details")
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str = "India"
    currency: str = "INR"
    monthly_rent: Decimal = Field(..., ge=0, description="Monthly rent in INR")
    security_deposit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Security deposit in INR")
    maintenance_monthly: Decimal = Field(default=Decimal("0.00"), ge=0, description="Maintenance in INR")
    bills_included: bool = False
    total_bedrooms: int = Field(default=1, ge=0)
    total_bathrooms: int = Field(default=1, ge=1)
    max_capacity: int = Field(default=2, ge=1)
    current_occupants: int = Field(default=0, ge=0)
    available_from: date
    is_furnished: bool = False
    furnishing_status: str = Field(default="semi_furnished", description="fully_furnished, semi_furnished, unfurnished")
    pets_allowed: bool = False
    smoking_allowed: bool = False
    images: List[str] = []
    amenities: List[str] = []

class PropertyCreate(PropertyBase):
    rooms: Optional[List[RoomCreate]] = []

class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    maintenance_monthly: Optional[Decimal] = None
    available_from: Optional[date] = None
    is_furnished: Optional[bool] = None
    furnishing_status: Optional[str] = None
    pets_allowed: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    images: Optional[List[str]] = None
    amenities: Optional[List[str]] = None
    current_occupants: Optional[int] = None
    listing_status: Optional[str] = None

class OwnerResponseTime(BaseModel):
    """How quickly the owner answers chats (last 90 days, shown from 3 chats)."""
    label: str
    reply_rate: float
    median_reply_minutes: Optional[int] = None
    chats: int


class PropertyResponse(PropertyBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    listing_status: str
    is_featured: bool = False
    # Only when searching near a point: km from it to the listing's shown (approximate) position.
    distance_km: Optional[float] = None
    # Only in the recommended order: up to two plain reasons, e.g. "Within your budget".
    match_reasons: List[str] = []
    # Only on a single listing: the owner's reply badge, once they have enough chats.
    owner_response: Optional[OwnerResponseTime] = None
    is_verified: bool
    is_active: bool
    rooms: List[RoomResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ListingStatusUpdate(BaseModel):
    listing_status: str = Field(..., description="draft, pending_verification, published, paused, archived")

class AssignOccupantRequest(BaseModel):
    occupant_id: uuid.UUID
