from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.flatmates.schemas import FlatmateSearchFilter, FlatmateSeekerCard
from app.modules.flatmates.service import FlatmateService

router = APIRouter(prefix="/flatmates", tags=["Flatmates"])

@router.get("/search", response_model=List[FlatmateSeekerCard])
async def search_flatmates(
    city: Optional[str] = Query(None),
    min_budget: Optional[int] = Query(None),
    max_budget: Optional[int] = Query(None),
    gender: Optional[str] = Query(None),
    sleep_schedule: Optional[str] = Query(None),
    cleanliness_min: Optional[int] = Query(None),
    diet: Optional[str] = Query(None),
    smoking: Optional[str] = Query(None),
    pets: Optional[str] = Query(None),
    q: Optional[str] = Query(None, max_length=300, description="Search people by what they wrote about themselves"),
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = FlatmateSearchFilter(
        city=city,
        min_budget=min_budget,
        max_budget=max_budget,
        gender=gender,
        sleep_schedule=sleep_schedule,
        cleanliness_min=cleanliness_min,
        diet=diet,
        smoking=smoking,
        pets=pets,
        q=q,
        limit=limit,
        offset=offset,
    )
    service = FlatmateService(db)
    return await service.search_flatmates(current_user.id, filters)
