"""
Group Matching & Shared Requirements Schemas
"""
import uuid
from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field

class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    model_config = ConfigDict(from_attributes=True)

class GroupWishlistItemResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    property_id: uuid.UUID
    added_by: uuid.UUID
    votes: Dict[str, str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class GroupBase(BaseModel):
    name: str = Field(..., description="e.g. Bangalore Tech Flatshare 3BHK")
    description: Optional[str] = None
    target_budget_total: int = Field(..., ge=0, description="Total cumulative group budget in INR")
    target_city: str
    target_move_in: Optional[date] = None

class GroupCreate(GroupBase):
    pass

class GroupResponse(GroupBase):
    id: uuid.UUID
    creator_id: uuid.UUID
    members: List[GroupMemberResponse] = []
    wishlist_items: List[GroupWishlistItemResponse] = []
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(default="member", description="leader, member")

class WishlistVoteRequest(BaseModel):
    vote: str = Field(..., description="up, down, neutral")

class PairwiseScoreItem(BaseModel):
    user_one_id: uuid.UUID
    user_one_name: str
    user_two_id: uuid.UUID
    user_two_name: str
    score: float
    dealbreakers_cleared: bool
    conflict_summary: Optional[str] = None

class GroupCompatibilityResponse(BaseModel):
    group_id: uuid.UUID
    total_members: int
    collective_score: float
    dealbreakers_cleared: bool
    pairwise_breakdowns: List[PairwiseScoreItem] = []
    group_conflicts: List[str] = []
    shared_strengths: List[str] = []
