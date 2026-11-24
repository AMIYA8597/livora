"""
Unit and Integration Tests for Property Domain, Accommodation Hierarchy,
Beds, Capacity Invariants, and Listing Lifecycle.
"""
from uuid import uuid4
from decimal import Decimal
from datetime import date
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.properties.schemas import PropertyCreate, RoomCreate
from app.modules.properties.service import PropertyService
from app.modules.properties.models import Property, Room, Bed
from app.core.exceptions import BadRequestException, ConflictException

@pytest.mark.asyncio
async def test_property_capacity_invariant_create_async():
    """Async test verifying rejection when occupants exceed max capacity."""
    owner_id = uuid4()
    mock_db = AsyncMock()
    service = PropertyService(mock_db)

    invalid_prop = PropertyCreate(
        title="2BHK in Indiranagar",
        description="Spacious flat",
        property_category="apartment",
        configuration="2BHK",
        latitude=12.9716,
        longitude=77.5946,
        address_display="Indiranagar 100ft Road, Bengaluru",
        address_exact="Flat 302, Palm Heights",
        city="Bengaluru",
        postal_code="560038",
        monthly_rent=Decimal("35000.00"),
        security_deposit=Decimal("100000.00"),
        total_bedrooms=2,
        total_bathrooms=2,
        max_capacity=2,
        current_occupants=3, # Invariant violated
        available_from=date.today(),
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service.create(owner_id, invalid_prop)
    assert "cannot exceed maximum capacity" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
@pytest.mark.usefixtures("stub_city_catalogue")
async def test_room_bed_capacity_invariant_rejection():
    """Room creation is rejected if occupied_beds > max_beds."""
    owner_id = uuid4()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = PropertyService(mock_db)

    invalid_room = RoomCreate(
        room_name="Shared Room A",
        room_type="2_sharing",
        room_rent=Decimal("8000.00"),
        max_beds=2,
        occupied_beds=3, # Exceeds max_beds!
        available_from=date.today(),
    )

    prop_data = PropertyCreate(
        title="PG Accommodation Koramangala",
        description="Bed sharing PG",
        property_category="pg",
        configuration="shared_room",
        latitude=12.9352,
        longitude=77.6245,
        address_display="Koramangala 4th Block, Bengaluru",
        address_exact="Plot 12, Sri Nilaya PG",
        city="Bengaluru",
        postal_code="560034",
        monthly_rent=Decimal("8000.00"),
        total_bedrooms=1,
        total_bathrooms=1,
        max_capacity=5,
        current_occupants=0,
        available_from=date.today(),
        rooms=[invalid_room],
    )

    with pytest.raises(BadRequestException) as exc_info:
        await service.create(owner_id, prop_data)
    assert "cannot exceed max beds" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
async def test_bed_assignment_and_conflict():
    """Verify bed assignment updates occupancy, and conflict is raised on already occupied bed."""
    owner_id = uuid4()
    occupant_id = uuid4()
    mock_db = AsyncMock()

    prop = Property(
        id=uuid4(),
        owner_id=owner_id,
        max_capacity=2,
        current_occupants=0,
    )
    room = Room(
        id=uuid4(),
        property_id=prop.id,
        max_beds=2,
        occupied_beds=0,
        property=prop,
    )
    bed = Bed(
        id=uuid4(),
        room_id=room.id,
        bed_identifier="Bed 1",
        monthly_rent=Decimal("7500.00"),
        available_from=date.today(),
        is_occupied=False,
        room=room,
    )

    service = PropertyService(mock_db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = bed
    mock_db.execute.return_value = mock_result

    # 1. Assign occupant to vacant bed
    assigned_bed = await service.assign_bed_occupant(bed.id, occupant_id, owner_id)
    assert assigned_bed.is_occupied is True
    assert assigned_bed.current_occupant_id == occupant_id
    assert room.occupied_beds == 1
    assert prop.current_occupants == 1

    # 2. Re-assigning to already occupied bed raises ConflictException
    with pytest.raises(ConflictException) as exc_info:
        await service.assign_bed_occupant(bed.id, uuid4(), owner_id)
    assert "already occupied" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
async def test_bed_vacating():
    """Vacating an occupied bed frees it and decrements occupant counts."""
    owner_id = uuid4()
    occupant_id = uuid4()
    mock_db = AsyncMock()

    prop = Property(id=uuid4(), owner_id=owner_id, max_capacity=2, current_occupants=1)
    room = Room(id=uuid4(), property_id=prop.id, max_beds=2, occupied_beds=1, property=prop)
    bed = Bed(
        id=uuid4(),
        room_id=room.id,
        bed_identifier="Bed 1",
        monthly_rent=Decimal("7500.00"),
        available_from=date.today(),
        is_occupied=True,
        current_occupant_id=occupant_id,
        room=room,
    )

    service = PropertyService(mock_db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = bed
    mock_db.execute.return_value = mock_result

    vacated_bed = await service.vacate_bed(bed.id, owner_id)
    assert vacated_bed.is_occupied is False
    assert vacated_bed.current_occupant_id is None
    assert room.occupied_beds == 0
    assert prop.current_occupants == 0

@pytest.mark.asyncio
async def test_listing_status_state_machine():
    """Verify listing status transitions and rejection of invalid statuses."""
    owner_id = uuid4()
    mock_db = AsyncMock()
    prop = Property(
        id=uuid4(),
        owner_id=owner_id,
        title="Independent 3BHK",
        listing_status="draft",
        max_capacity=4,
        current_occupants=0,
    )

    service = PropertyService(mock_db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prop
    mock_db.execute.return_value = mock_result
    service.get_by_id = AsyncMock(return_value={"id": prop.id, "listing_status": "published"})

    # 1. Valid transition to 'published'
    await service.update_listing_status(prop.id, owner_id, "published")
    assert prop.listing_status == "published"

    # 2. Invalid status rejection
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_listing_status(prop.id, owner_id, "invalid_custom_status")
    assert "invalid listing status" in str(exc_info.value.detail).lower()
