from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from app.modules.applications.schemas import ApplicationResponse

class OwnerDashboardStats(BaseModel):
    total_properties: int
    active_listings: int
    pending_applications: int
    total_inquiries: int
    estimated_monthly_revenue: Decimal

class ApplicantReviewCard(BaseModel):
    application: ApplicationResponse
    applicant_name: str
    applicant_email: str
    applicant_occupation: Optional[str] = None
    applicant_avatar: Optional[str] = None
    is_verified: bool
    property_title: str

class TenantRosterItem(BaseModel):
    membership_id: str
    tenant_id: str
    tenant_name: str
    tenant_email: str
    room_name: Optional[str] = None
    bed_identifier: Optional[str] = None
    monthly_rent: Decimal
    status: str
    is_primary_tenant: bool
