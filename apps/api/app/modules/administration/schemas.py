"""
Administration Schemas
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class AdminUserListItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AdminUserStatusUpdate(BaseModel):
    is_active: bool
    reason: Optional[str] = None

class AdminRoleGrant(BaseModel):
    role: str = Field(..., description="owner, pg_operator, broker, moderator, admin")

class PlatformStatsResponse(BaseModel):
    total_users: int
    total_properties: int
    total_active_listings: int
    total_mutual_matches: int
    pending_verifications: int
    open_moderation_reports: int



class AdminBillingEventItem(BaseModel):
    """A stored payment-provider webhook delivery. The payload itself (customer contact details)
    stays out; `subscription_ref` is the provider's subscription id it is about."""
    id: uuid.UUID
    provider: str
    event_id: str
    event_type: str
    status: str
    error: Optional[str] = None
    subscription_ref: Optional[str] = None
    received_at: datetime
    processed_at: Optional[datetime] = None

    @classmethod
    def of(cls, ev) -> "AdminBillingEventItem":
        entity = (((ev.payload or {}).get("payload") or {}).get("subscription") or {}).get("entity") or {}
        ref = entity.get("id")
        return cls(id=ev.id, provider=ev.provider, event_id=ev.event_id, event_type=ev.event_type,
                   status=ev.status, error=ev.error, subscription_ref=ref if isinstance(ref, str) else None,
                   received_at=ev.received_at, processed_at=ev.processed_at)


class AdminApplicationListItem(BaseModel):
    id: uuid.UUID
    status: str
    applicant_id: uuid.UUID
    applicant_name: str
    applicant_email: str
    property_id: uuid.UUID
    property_title: str
    owner_name: Optional[str] = None
    proposed_rent: Decimal
    submitted_at: datetime
    updated_at: datetime
