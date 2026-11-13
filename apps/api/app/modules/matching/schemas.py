"""
Matching Schemas
Supports 10-dimension factor breakdowns, interaction requests, and mutual match notifications.
"""
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.modules.profiles.schemas import ProfileResponse

class ScoreBreakdownSchema(BaseModel):
    overall_score: float
    factors: Dict[str, int] = {}
    explanations: Dict[str, str] = {}
    dealbreakers_cleared: bool
    conflicts: List[str] = []
    algorithm_version: str = "v1.0-india-heuristic"
    shared_interests: List[str] = []

class FlatmateMatchResponse(BaseModel):
    profile: ProfileResponse
    match_score: ScoreBreakdownSchema

class MatchInteractionRequest(BaseModel):
    target_user_id: uuid.UUID
    action: str = Field(..., description="like, pass, save, super_like")

class MatchInteractionResponse(BaseModel):
    interaction_id: uuid.UUID
    user_id: uuid.UUID
    target_user_id: uuid.UUID
    action: str
    is_mutual_match: bool
    mutual_match_id: Optional[uuid.UUID] = None
    compatibility_score: Optional[float] = None

class MutualMatchItemResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    partner_name: str
    partner_avatar: Optional[str] = None
    partner_occupation: Optional[str] = None
    compatibility_score: float
    algorithm_version: str
    score_breakdown: Dict[str, Any]
    status: str
    model_config = ConfigDict(from_attributes=True)
