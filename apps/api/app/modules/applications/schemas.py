import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

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
    status: str # "reviewing", "accepted", "rejected", "withdrawn"
    note: Optional[str] = None

class ApplicationResponse(ApplicationBase):
    id: uuid.UUID
    applicant_id: uuid.UUID
    status: str
    submitted_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
