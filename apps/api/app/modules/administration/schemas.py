"""
Administration Schemas
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class AdminUserListItem(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    # Every role the account holds (the primary one included).
    roles: List[str] = []
    is_active: bool
    is_verified: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("roles", mode="before")
    @classmethod
    def _role_names(cls, v):
        return [getattr(r, "role", r) for r in (v or [])]

    @model_validator(mode="after")
    def _include_primary_role(self):
        self.roles = sorted(set(self.roles) | {self.role})
        return self

class AdminUserStatusUpdate(BaseModel):
    is_active: bool
    reason: Optional[str] = None

class AdminRoleGrant(BaseModel):
    role: str = Field(..., max_length=32, description="seeker, tenant, owner, pg_operator, broker, moderator, admin, super_admin")

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


class AdminRoleRequestItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    user_roles: List[str]
    role: str
    status: str
    note: Optional[str] = None
    decision_note: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


class RoleRequestDecision(BaseModel):
    approve: bool
    # Required when declining: the person sees it.
    note: Optional[str] = Field(default=None, max_length=500)



# ---------------------------------------------------------------- live traffic (GET /admin/traffic)

class TrafficLatency(BaseModel):
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None


class TrafficStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: int = Field(0, alias="2xx")
    redirect: int = Field(0, alias="3xx")
    client_error: int = Field(0, alias="4xx")
    server_error: int = Field(0, alias="5xx")


class TrafficPool(BaseModel):
    checked_out: int = 0
    limit: int = 0


class TrafficRoute(BaseModel):
    route: str
    requests: int
    errors: int
    p95_ms: Optional[float] = None


class TrafficInstance(BaseModel):
    instance: Optional[str] = None
    uptime_seconds: Optional[int] = None
    requests: int = 0
    in_flight: int = 0
    websockets: int = 0
    loop_lag_ms: float = 0.0
    db_pool: Dict[str, int] = {}


class TrafficSnapshot(BaseModel):
    scope: Literal["all_instances", "this_instance"]
    window_seconds: int
    instances: int
    requests: int
    requests_per_second: float
    status: TrafficStatus
    error_rate: float
    latency_ms: TrafficLatency
    shed: int
    timeouts: int
    unavailable: int
    in_flight: int
    websockets: int
    loop_lag_ms: float = 0.0
    db_pool: TrafficPool
    routes: List[TrafficRoute]
    per_instance: List[TrafficInstance]
