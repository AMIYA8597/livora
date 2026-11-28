import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator

ApplicationStatus = Literal["submitted", "under_review", "reviewing", "accepted", "approved", "rejected", "withdrawn"]

class ApplicationBase(BaseModel):
    property_id: uuid.UUID
    room_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    introduction: str
    proposed_rent: Decimal
    move_in_target: date
    documents: List[str] = []

MAX_PROPOSED_RENT = Decimal("10000000")  # ₹1 crore a month; the column holds up to 10 digits
MAX_MOVE_IN_DAYS_AHEAD = 730


class ApplicationCreate(ApplicationBase):
    """What an applicant may send. The checks live here, not on ApplicationBase, because
    ApplicationResponse shares that base and must still read applications stored earlier."""

    introduction: str = Field(..., max_length=2000)
    proposed_rent: Decimal = Field(..., gt=0, le=MAX_PROPOSED_RENT, decimal_places=2)
    documents: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("introduction")
    @classmethod
    def _introduction_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Introduce yourself to the landlord")
        return value

    @field_validator("move_in_target")
    @classmethod
    def _move_in_not_past(cls, value: date) -> date:
        # A day of slack: the applicant's "today" (India) can be a day ahead of the server's (UTC).
        today = datetime.now(timezone.utc).date()
        if value < today - timedelta(days=1):
            raise ValueError("Move-in date can't be in the past")
        if value > today + timedelta(days=MAX_MOVE_IN_DAYS_AHEAD):
            raise ValueError("Move-in date must be within two years")
        return value

    @field_validator("documents")
    @classmethod
    def _documents_short(cls, value: List[str]) -> List[str]:
        if any(len(item) > 500 for item in value):
            raise ValueError("Document references must be at most 500 characters")
        return value

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

class PartyStatusEventResponse(BaseModel):
    """A status change as the applicant and the owner see it: who acted is a role, never a staff
    member's name, and staff reasons stay with staff (parties are told only that support acted)."""
    from_status: Optional[str] = None  # None for the submission itself
    to_status: str
    actor: Literal["applicant", "owner", "support", "unknown"]
    created_at: datetime


class ApplicationResponse(ApplicationBase):
    id: uuid.UUID
    applicant_id: uuid.UUID
    status: str
    submitted_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
