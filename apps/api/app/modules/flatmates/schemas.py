import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class FlatmateSearchFilter(BaseModel):
    city: Optional[str] = None
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None
    gender: Optional[str] = None
    sleep_schedule: Optional[str] = None
    cleanliness_min: Optional[int] = None
    diet: Optional[str] = None
    smoking: Optional[str] = None
    pets: Optional[str] = None
    q: Optional[str] = None  # "about me" search, ordered by relevance
    limit: int = 20
    offset: int = 0

class FlatmateSeekerCard(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    age: Optional[int] = None
    occupation: Optional[str] = None
    budget_min: int
    budget_max: int
    preferred_locations: List[str]
    lifestyle_traits: Dict[str, Any]
    is_verified: bool
