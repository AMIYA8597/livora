"""
Unit and Integration Tests for Owner Roster, Tenant Vacancies, and PG Accommodation Workflows.
"""
from uuid import uuid4
from decimal import Decimal
from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.owners.service import OwnerService
from app.modules.tenants.schemas import ExistingTenantVacancyCreate
from app.modules.tenants.service import TenantService
from app.modules.tenants.models import TenantMembership
from app.modules.pg_management.schemas import PGBuildingCreate, PGFloorCreate
from app.modules.pg_management.service import PGService
from app.modules.pg_management.models import PGBuilding
from app.modules.properties.models import Property, Room, Bed
from app.modules.users.models import User
from app.core.exceptions import ForbiddenException, ConflictException

@pytest.mark.asyncio
async def test_owner_tenant_roster_access_and_security():
    """Owner can retrieve tenant roster; non-owner access is rejected."""
    owner_id = uuid4()
    stranger_id = uuid4()
    prop_id = uuid4()

    mock_db = AsyncMock()
    service = OwnerService(mock_db)

    prop = Property(id=prop_id, owner_id=owner_id, title="3BHK Villa")
    mock_prop_res = MagicMock()
    mock_prop_res.scalar_one_or_none.return_value = prop

    tenant_user = User(id=uuid4(), email="tenant@example.com", full_name="Aarav Sharma")
    membership = TenantMembership(
        id=uuid4(),
        property_id=prop_id,
        tenant_id=tenant_user.id,
        monthly_rent=Decimal("12000.00"),
        status="active",
        is_primary_tenant=True,
    )
    room = Room(id=uuid4(), property_id=prop_id, room_name="Bedroom 1")
    bed = Bed(id=uuid4(), room_id=room.id, bed_identifier="Bed A")

    mock_roster_res = MagicMock()
    mock_roster_res.all.return_value = [(membership, tenant_user, room, bed)]

    # 1. Non-owner gets ForbiddenException
    mock_db.execute.return_value = mock_prop_res
    with pytest.raises(ForbiddenException) as exc_info:
        await service.get_property_tenants(owner_id=stranger_id, property_id=prop_id, is_admin=False)
    assert "access denied" in str(exc_info.value.detail).lower()

    # 2. Real owner gets roster
    mock_db.execute.side_effect = [mock_prop_res, mock_roster_res]
    roster = await service.get_property_tenants(owner_id=owner_id, property_id=prop_id, is_admin=False)
    assert len(roster) == 1
    assert roster[0].tenant_name == "Aarav Sharma"
    assert roster[0].monthly_rent == Decimal("12000.00")
    assert roster[0].room_name == "Bedroom 1"

@pytest.mark.asyncio
async def test_existing_tenant_vacancy_authorization():
    """Only active tenants of a property can post a flatmate vacancy."""
    tenant_id = uuid4()
    non_tenant_id = uuid4()
    prop_id = uuid4()
    room_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = TenantService(mock_db)

    vacancy_data = ExistingTenantVacancyCreate(
        property_id=prop_id,
        room_id=room_id,
        title="Looking for chill flatmate in 3BHK",
        description="Furnished private room available from next month.",
        vacant_from=date.today(),
        expected_rent=Decimal("14000.00"),
        deposit_required=Decimal("40000.00"),
        preferred_gender="female_only",
    )

    # 1. Non-tenant attempt raises ForbiddenException
    mock_empty_res = MagicMock()
    mock_empty_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_empty_res

    with pytest.raises(ForbiddenException) as exc_info:
        await service.create_vacancy(tenant_id=non_tenant_id, data=vacancy_data)
    assert "active tenant" in str(exc_info.value.detail).lower()

    # 2. Active tenant success
    active_membership = TenantMembership(
        id=uuid4(),
        property_id=prop_id,
        tenant_id=tenant_id,
        status="active",
        monthly_rent=Decimal("14000.00")
    )
    mock_active_res = MagicMock()
    mock_active_res.scalar_one_or_none.return_value = active_membership
    mock_db.execute.return_value = mock_active_res

    created = await service.create_vacancy(tenant_id=tenant_id, data=vacancy_data)
    assert created.property_id == prop_id
    assert created.expected_rent == Decimal("14000.00")
    assert created.preferred_gender == "female_only"
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_pg_building_management_and_duplicate_prevention():
    """PG Operator can register building with meal plans, curfews, and floors."""
    operator_id = uuid4()
    prop_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = PGService(mock_db)

    pg_input = PGBuildingCreate(
        property_id=prop_id,
        building_name="Zolo Comfort PG",
        pg_type="gents",
        total_floors=2,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="23:00",
        notice_period_days=30,
        biometric_entry=True,
        floors=[
            PGFloorCreate(floor_number=1, gender_restriction="male_only", total_rooms=4),
            PGFloorCreate(floor_number=2, gender_restriction="male_only", total_rooms=4),
        ]
    )

    # 1. Duplicate PG registration on same property raises ConflictException
    existing_pg = PGBuilding(id=uuid4(), property_id=prop_id, operator_id=operator_id)
    mock_exist_res = MagicMock()
    mock_exist_res.scalar_one_or_none.return_value = existing_pg
    mock_db.execute.return_value = mock_exist_res

    with pytest.raises(ConflictException) as exc_info:
        await service.create_building(operator_id=operator_id, data=pg_input)
    assert "already registered" in str(exc_info.value.detail).lower()

    # 2. Successful creation when not duplicate
    mock_none_res = MagicMock()
    mock_none_res.scalar_one_or_none.return_value = None

    created_building = PGBuilding(
        id=uuid4(),
        operator_id=operator_id,
        property_id=prop_id,
        building_name="Zolo Comfort PG",
        pg_type="gents",
        total_floors=2,
        food_included=True,
        meal_type="veg_and_non_veg",
        meals_served_per_day=3,
        gate_closing_time="23:00",
        notice_period_days=30,
        biometric_entry=True,
        floors=[],
    )
    mock_get_res = MagicMock()
    mock_get_res.scalar_one_or_none.return_value = created_building

    mock_db.execute.side_effect = [mock_none_res, mock_get_res]
    result = await service.create_building(operator_id=operator_id, data=pg_input)
    assert result.building_name == "Zolo Comfort PG"
    assert result.food_included is True
    assert result.gate_closing_time == "23:00"
