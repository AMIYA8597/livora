"""
Moderation Schemas
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class ReportCreate(BaseModel):
    target_type: str = Field(..., description="user, property, message")
    target_id: uuid.UUID
    reason: str
    description: Optional[str] = None

class ReportResponse(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ReportReviewRequest(BaseModel):
    status: str = Field(..., description="under_investigation, resolved, dismissed")
    action_taken: Optional[str] = Field(default=None, description="none, warn_user, suspend_user, remove_listing")

class BlockUserResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    blocked_user_id: uuid.UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
