"""
Paying Guest (PG) Service
Manages PG Buildings, Floor wings, Gender rules, Meals, and Curfews.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.modules.pg_management.models import PGBuilding, PGFloor
from app.modules.pg_management.schemas import PGBuildingCreate, PGFloorCreate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException

class PGService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_building(self, pg_id: UUID) -> Optional[PGBuilding]:
        query = (
            select(PGBuilding)
            .options(selectinload(PGBuilding.floors))
            .where(PGBuilding.id == pg_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_building(self, operator_id: UUID, data: PGBuildingCreate) -> PGBuilding:
        # Check if building record already exists for this property
        existing_q = select(PGBuilding).where(PGBuilding.property_id == data.property_id)
        existing = (await self.db.execute(existing_q)).scalar_one_or_none()
        if existing:
            raise ConflictException("A PG building configuration is already registered for this property")

        building = PGBuilding(
            operator_id=operator_id,
            property_id=data.property_id,
            building_name=data.building_name,
            pg_type=data.pg_type,
            total_floors=data.total_floors,
            food_included=data.food_included,
            meal_type=data.meal_type,
            meals_served_per_day=data.meals_served_per_day,
            gate_closing_time=data.gate_closing_time,
            notice_period_days=data.notice_period_days,
            biometric_entry=data.biometric_entry,
        )
        self.db.add(building)
        await self.db.flush()

        if data.floors:
            for f_data in data.floors:
                floor = PGFloor(
                    pg_building_id=building.id,
                    floor_number=f_data.floor_number,
                    gender_restriction=f_data.gender_restriction,
                    total_rooms=f_data.total_rooms,
                )
                self.db.add(floor)

        await self.db.commit()
        created = await self.get_building(building.id)
        if not created:
            raise NotFoundException("PG Building not found after creation")
        return created

    async def list_buildings(
        self,
        operator_id: Optional[UUID] = None,
        pg_type: Optional[str] = None,
        food_included: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[PGBuilding]:
        query = select(PGBuilding).options(selectinload(PGBuilding.floors))
        if operator_id:
            query = query.where(PGBuilding.operator_id == operator_id)
        if pg_type:
            query = query.where(PGBuilding.pg_type == pg_type)
        if food_included is not None:
            query = query.where(PGBuilding.food_included.is_(food_included))

        query = query.order_by(PGBuilding.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_floor(self, pg_id: UUID, operator_id: UUID, data: PGFloorCreate, is_admin: bool = False) -> PGFloor:
        building = await self.get_building(pg_id)
        if not building:
            raise NotFoundException("PG Building not found")
        if building.operator_id != operator_id and not is_admin:
            raise ForbiddenException("Access denied to modify this PG building")

        floor = PGFloor(
            pg_building_id=pg_id,
            floor_number=data.floor_number,
            gender_restriction=data.gender_restriction,
            total_rooms=data.total_rooms,
        )
        self.db.add(floor)
        await self.db.commit()
        await self.db.refresh(floor)
        return floor
