"""
The location catalogue (migration 016): India's states and union territories, their capitals and
the other cities listings may use, plus the names people also search by (Bangalore, Port Blair).
Listings are saved under the official city name, and searches by any name find them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.locations.models import City, Country, State


@dataclass(frozen=True)
class CatalogueCity:
    slug: str
    name: str
    state: str
    state_code: str
    state_kind: str
    is_capital: bool
    tier: int
    latitude: Optional[float]
    longitude: Optional[float]
    aliases: tuple
    is_active: bool = True


def _key(name: str) -> str:
    return " ".join(name.split()).casefold()


class LocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def cities(self, active_only: bool = True) -> List[CatalogueCity]:
        """Every catalogue city, grouped by state name then city name."""
        capitals = select(State.capital_city_id).where(State.capital_city_id.is_not(None))
        query = (
            select(City, State,
                   func.ST_Y(City.center_location).label("lat"), func.ST_X(City.center_location).label("lng"),
                   City.id.in_(capitals).label("is_capital"))
            .join(State, State.id == City.state_id)
            .join(Country, Country.id == State.country_id)
            .where(Country.code == "IND")
            .order_by(State.name, City.name)
        )
        if active_only:
            query = query.where(City.is_active.is_(True))
        rows = (await self.db.execute(query)).all()
        return [
            CatalogueCity(slug=c.slug, name=c.name, state=s.name, state_code=s.code, state_kind=s.kind,
                          is_capital=bool(cap), tier=c.tier, latitude=lat, longitude=lng,
                          aliases=tuple(c.aliases or ()), is_active=c.is_active)
            for c, s, lat, lng, cap in rows
        ]

    async def states(self) -> List[dict]:
        capital = City.__table__.alias("capital")
        rows = (await self.db.execute(
            select(State.code, State.name, State.kind, capital.c.name, capital.c.slug)
            .join(Country, Country.id == State.country_id)
            .outerjoin(capital, capital.c.id == State.capital_city_id)
            .where(Country.code == "IND")
            .order_by(State.kind, State.name)
        )).all()
        return [dict(code=code, name=name, kind=kind, capital=cap, capital_slug=slug)
                for code, name, kind, cap, slug in rows]

    async def resolve(self, name: Optional[str]) -> Optional[CatalogueCity]:
        """The catalogue city a name refers to (its official name or an alias), or None."""
        if not name or not name.strip():
            return None
        key = _key(name)
        for city in await self.cities(active_only=False):
            if _key(city.name) == key or _key(city.slug.replace("-", " ")) == key \
                    or any(_key(a) == key for a in city.aliases):
                return city
        return None


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres (haversine; within 0.5% of PostGIS's spheroid)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))


async def nearest_city(db: AsyncSession, lat: float, lng: float) -> Optional[Tuple[CatalogueCity, float]]:
    """The open catalogue city closest to a point, and how far it is (km)."""
    best: Optional[Tuple[CatalogueCity, float]] = None
    for city in await LocationService(db).cities():
        if city.latitude is None or city.longitude is None:
            continue
        d = distance_km(lat, lng, city.latitude, city.longitude)
        if best is None or d < best[1]:
            best = (city, d)
    return best


async def city_condition(db: AsyncSession, column, value: str):
    """A filter on a city column: any name of a catalogue city (Bangalore, Bengaluru) matches its
    listings exactly; anything else (a partly typed name) is matched as text."""
    city = await LocationService(db).resolve(value)
    return column == city.name if city else column.icontains(value.strip(), autoescape=True)
