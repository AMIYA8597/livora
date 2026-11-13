"""
Administration Schemas
"""
import uuid
from datetime import datetime
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
