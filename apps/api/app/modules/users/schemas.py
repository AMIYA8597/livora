import uuid
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone_number: Optional[str] = None
    role: str = "seeker"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    # Internal timestamp; clients get the boolean below.
    phone_verified_at: Optional[datetime] = Field(default=None, exclude=True)
    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def phone_verified(self) -> bool:
        return self.phone_verified_at is not None


class RoleRequestCreate(BaseModel):
    role: Literal["broker"]
    # Agency, RERA registration, city: whatever helps staff check who you are.
    note: Optional[str] = Field(default=None, max_length=500)


class RoleRequestResponse(BaseModel):
    id: uuid.UUID
    role: str
    status: str
    note: Optional[str] = None
    decision_note: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

