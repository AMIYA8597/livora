import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EmailVerificationType = Literal["work_email", "student_email"]


class SendEmailCodeRequest(BaseModel):
    verification_type: EmailVerificationType
    email: str = Field(..., min_length=3, max_length=254)


class ConfirmEmailCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class VerifiedItem(BaseModel):
    verification_type: str
    email_domain: Optional[str] = None
    verified_at: Optional[datetime] = None


class PendingEmailCode(BaseModel):
    verification_type: str
    email_domain: str
    expires_at: datetime


class UserTrustScoreResponse(BaseModel):
    user_id: uuid.UUID
    total_trust_score: int
    badges: List[str]
    # Mobile number and a work or college email both verified.
    is_fully_verified: bool
    phone_verified: bool = False
    verifications: List[VerifiedItem] = []
    pending: Optional[PendingEmailCode] = None
    # ID-document checks are off until a KYC provider is integrated.
    id_verification_available: bool = False


class SendEmailCodeResponse(BaseModel):
    success: bool = True
    message: str
    email_domain: str
    already_verified: bool = False
    expires_in: Optional[int] = None
    resend_after: Optional[int] = None
    dev_code: Optional[str] = None
