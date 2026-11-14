"""
Paying Guest (PG) Router
REST endpoints for PG operations, floor allocations, meal systems, and curfew configurations.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.pg_management.schemas import (
    PGBuildingCreate,
    PGBuildingResponse,
    PGFloorCreate,
    PGFloorResponse,
)
from app.modules.pg_management.service import PGService

router = APIRouter(prefix="/pg", tags=["PG Management"])

@router.post("/buildings", response_model=PGBuildingResponse, status_code=status.HTTP_201_CREATED)
async def create_pg_building(
    data: PGBuildingCreate,
    current_user: User = Depends(require_roles(["pg_operator", "owner", "admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = PGService(db)
    return await service.create_building(current_user.id, data)

@router.get("/buildings", response_model=List[PGBuildingResponse])
async def list_pg_buildings(
    pg_type: Optional[str] = Query(None, description="gents, ladies, coed"),
    food_included: Optional[bool] = Query(None, description="Filter by food included"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = PGService(db)
    return await service.list_buildings(pg_type=pg_type, food_included=food_included, limit=limit, offset=offset)

@router.get("/buildings/{pg_id}", response_model=PGBuildingResponse)
async def get_pg_building(
    pg_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = PGService(db)
    building = await service.get_building(pg_id)
    if not building:
        raise NotFoundException("PG Building not found")
    return building

@router.post("/buildings/{pg_id}/floors", response_model=PGFloorResponse, status_code=status.HTTP_201_CREATED)
async def add_pg_floor(
    pg_id: UUID,
    data: PGFloorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = PGService(db)
    return await service.add_floor(pg_id, current_user.id, data, is_admin=is_admin)
