"""
Tenants Domain Schemas
Covers Tenancy Memberships, Active Leases, and Existing Tenant Flatmate Vacancies.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class TenantMembershipResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: Optional[uuid.UUID] = None
    bed_id: Optional[uuid.UUID] = None
    tenant_id: uuid.UUID
    lease_start: date
    lease_end: Optional[date] = None
    monthly_rent: Decimal
    status: str
    is_primary_tenant: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExistingTenantVacancyCreate(BaseModel):
    property_id: uuid.UUID
    room_id: uuid.UUID
    title: str = Field(..., description="e.g. Need 1 flatmate for master bedroom in 3BHK HSR Layout")
    description: str = Field(..., description="Room and flatmate requirements")
    vacant_from: date
    expected_rent: Decimal = Field(..., ge=0, description="Monthly rent share in INR")
    deposit_required: Decimal = Field(default=Decimal("0.00"), ge=0, description="Deposit share in INR")
    preferred_gender: str = Field(default="any", description="any, female_only, male_only")

class ExistingTenantVacancyResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID
    posted_by_tenant_id: uuid.UUID
    title: str
    description: str
    vacant_from: date
    expected_rent: Decimal
    deposit_required: Decimal
    preferred_gender: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
