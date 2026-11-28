"""
Group Matching & Shared Requirements Schemas
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict, Field, field_validator

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

MAX_GROUP_BUDGET = 10_000_000  # ₹1 crore a month
MAX_MOVE_IN_DAYS_AHEAD = 730


class GroupCreate(GroupBase):
    """What a new group may say. The checks live here, not on GroupBase, because GroupResponse
    shares that base and must still read groups stored earlier. Lengths match the columns."""

    name: str = Field(..., max_length=120, description="e.g. Bangalore Tech Flatshare 3BHK")
    description: Optional[str] = Field(None, max_length=2000)
    target_budget_total: int = Field(..., gt=0, le=MAX_GROUP_BUDGET, description="Total cumulative group budget in INR")
    target_city: str = Field(..., max_length=100)

    @field_validator("name", "target_city")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Can't be blank")
        return value

    @field_validator("target_move_in")
    @classmethod
    def _move_in_ahead(cls, value: Optional[date]) -> Optional[date]:
        if value is None:
            return value
        # A day of slack: the person's "today" (India) can be a day ahead of the server's (UTC).
        today = datetime.now(timezone.utc).date()
        if value < today - timedelta(days=1):
            raise ValueError("Move-in date can't be in the past")
        if value > today + timedelta(days=MAX_MOVE_IN_DAYS_AHEAD):
            raise ValueError("Move-in date must be within two years")
        return value

class GroupResponse(GroupBase):
    """Members, the creator and the wishlist (whose votes are keyed by user) are shown only to
    the group's members and staff; everyone else sees the count."""
    id: uuid.UUID
    creator_id: Optional[uuid.UUID] = None
    member_count: int = 0
    is_member: bool = False
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
