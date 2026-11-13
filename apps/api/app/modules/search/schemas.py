"""
Search & Discovery Schemas
Defines structured filters and response items for Properties and Flatmates.
"""
import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PropertySearchFilter(BaseModel):
    query: Optional[str] = Field(default=None, description="Free text search across title, description, locality")
    latitude: Optional[float] = Field(default=None, description="Center GPS latitude")
    longitude: Optional[float] = Field(default=None, description="Center GPS longitude")
    radius_km: float = Field(default=15.0, ge=1.0, le=100.0, description="Search radius in kilometers")
    city: Optional[str] = None
    property_category: Optional[str] = Field(default=None, description="apartment, independent_house, pg, hostel, co_living")
    configuration: Optional[str] = Field(default=None, description="1RK, 1BHK, 2RK, 2BHK, 3BHK, 4BHK_plus, studio")
    min_rent: Optional[Decimal] = Field(default=None, ge=0)
    max_rent: Optional[Decimal] = Field(default=None, ge=0)
    furnishing_status: Optional[str] = Field(default=None, description="fully_furnished, semi_furnished, unfurnished")
    pets_allowed: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)

class PropertySearchResultItem(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    property_category: str
    configuration: str
    address_display: str
    city: str
    state: Optional[str] = None
    postal_code: str
    currency: str = "INR"
    monthly_rent: Decimal
    security_deposit: Decimal
    total_bedrooms: int
    total_bathrooms: int
    max_capacity: int
    current_occupants: int
    furnishing_status: str
    images: List[str] = []
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    is_fuzzed_location: bool = True

class FlatmateSearchFilter(BaseModel):
    city: Optional[str] = None
    locality: Optional[str] = Field(default=None, description="Locality within city (e.g. Koramangala, Indiranagar)")
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None
    gender: Optional[str] = None
    occupation: Optional[str] = None
    sleep_schedule: Optional[str] = None
    diet_preference: Optional[str] = None
    smoking: Optional[str] = None
    limit: int = Field(default=20, le=100)
    offset: int = Field(default=0, ge=0)

class FlatmateSearchResultItem(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    company_name: Optional[str] = None
    education_institute: Optional[str] = None
    budget_min: int
    budget_max: int
    preferred_locations: List[str] = []
    lifestyle_traits: Dict[str, Any] = {}
    is_verified: bool = False
