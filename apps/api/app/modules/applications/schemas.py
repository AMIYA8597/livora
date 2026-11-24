import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field

ApplicationStatus = Literal["submitted", "under_review", "reviewing", "accepted", "approved", "rejected", "withdrawn"]

class ApplicationBase(BaseModel):
    property_id: uuid.UUID
    room_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    introduction: str
    proposed_rent: Decimal
    move_in_target: date
    documents: List[str] = []

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    # Required when staff override a status (the reason goes in the application's history).
    note: Optional[str] = Field(None, max_length=500)

class ApplicationStatusEventResponse(BaseModel):
    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    from_status: str
    to_status: str
    note: Optional[str] = None
    by_staff: bool
    created_at: datetime

class ApplicationResponse(ApplicationBase):
    id: uuid.UUID
    applicant_id: uuid.UUID
    status: str
    submitted_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
