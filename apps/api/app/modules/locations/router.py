"""Public, cacheable location lists for pickers and search (no sign-in needed)."""
from typing import List

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.locations.schemas import CityOut, StateOut
from app.modules.locations.service import LocationService

router = APIRouter(prefix="/locations", tags=["Locations"])

# Changes only with a migration; browsers and CDNs may keep it for an hour.
CACHE = "public, max-age=3600, stale-while-revalidate=86400"


@router.get("/cities", response_model=List[CityOut])
async def list_cities(response: Response, db: AsyncSession = Depends(get_db)):
    """Cities open for listings: every state and union territory capital, plus other major cities."""
    response.headers["Cache-Control"] = CACHE
    return [CityOut(**{**c.__dict__, "aliases": list(c.aliases)}) for c in await LocationService(db).cities()]


@router.get("/states", response_model=List[StateOut])
async def list_states(response: Response, db: AsyncSession = Depends(get_db)):
    """India's 28 states and 8 union territories, with their capitals."""
    response.headers["Cache-Control"] = CACHE
    return await LocationService(db).states()
