from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.core.roles import SELF_SERVICE_ROLES
from app.modules.users.schemas import UserResponse

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(min_length=2)
    role: str = "seeker" # default primary role
    additional_roles: Optional[List[str]] = Field(default=None, max_length=len(SELF_SERVICE_ROLES))
    phone_number: Optional[str] = None

    @field_validator("role")
    @classmethod
    def _self_service_role(cls, v: str) -> str:
        # Staff roles and brokers are granted by staff, never chosen at sign-up.
        if v not in SELF_SERVICE_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(SELF_SERVICE_ROLES))}")
        return v

    @field_validator("additional_roles")
    @classmethod
    def _self_service_roles(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        bad = sorted(set(v or []) - SELF_SERVICE_ROLES)
        if bad:
            raise ValueError(f"roles not available at sign-up: {', '.join(bad)}")
        return v

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    roles: List[str]
    # True when this sign-in cancelled a pending account deletion.
    account_restored: bool = False

class CurrentUserResponse(UserResponse):
    """/auth/me: the user plus every role they hold, so clients never trust stored roles."""
    roles: List[str] = []

    @field_validator("roles", mode="before")
    @classmethod
    def _role_names(cls, v):
        return [getattr(r, "role", r) for r in (v or [])]

    @model_validator(mode="after")
    def _include_primary_role(self):
        self.roles = sorted(set(self.roles) | {self.role})
        return self

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SendOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20, description="E.164 or 10-digit Indian mobile number")

class VerifyOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=20)
    otp_code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, description="New password must be at least 8 characters")
