import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class SubmitVerificationRequest(BaseModel):
    verification_type: str # government_id, student_email, work_email, background_check
    document_url: Optional[str] = None

class VerificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    verification_type: str
    status: str
    document_url: Optional[str] = None
    trust_score_bonus: int
    verified_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserTrustScoreResponse(BaseModel):
    user_id: uuid.UUID
    total_trust_score: int
    badges: List[str]
    is_fully_verified: bool
