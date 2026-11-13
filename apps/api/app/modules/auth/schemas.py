from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from app.modules.users.schemas import UserResponse

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(min_length=2)
    role: str = "seeker" # default primary role
    additional_roles: Optional[List[str]] = None
    phone_number: Optional[str] = None

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

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SendOtpRequest(BaseModel):
    phone_number: str = Field(min_length=10, max_length=15, description="E.164 or 10-digit Indian mobile number")

class VerifyOtpRequest(BaseModel):
    phone_number: str
    otp_code: str = Field(min_length=4, max_length=6)
