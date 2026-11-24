"""Public location data: the states, union territories and cities listings can be in."""
from typing import List, Literal, Optional

from pydantic import BaseModel


class CityOut(BaseModel):
    slug: str
    name: str
    state: str
    state_code: str
    state_kind: Literal["state", "union_territory"]
    is_capital: bool
    tier: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    aliases: List[str] = []


class NearestCityOut(BaseModel):
    city: CityOut
    distance_km: float


class StateOut(BaseModel):
    code: str
    name: str
    kind: Literal["state", "union_territory"]
    capital: Optional[str] = None  # the capital city's name
    capital_slug: Optional[str] = None
