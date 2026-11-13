"""
Property Viewing Appointments Schemas
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class AppointmentBase(BaseModel):
    property_id: uuid.UUID
    room_id: Optional[uuid.UUID] = None
    host_id: uuid.UUID
    appointment_type: str = Field(default="physical_visit", description="physical_visit, video_call")
    scheduled_at: datetime
    meeting_link: Optional[str] = None
    notes: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentStatusUpdate(BaseModel):
    status: str = Field(..., description="confirmed, completed, cancelled, rescheduled")
    cancellation_reason: Optional[str] = None

class AppointmentResponse(AppointmentBase):
    id: uuid.UUID
    applicant_id: uuid.UUID
    status: str
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
