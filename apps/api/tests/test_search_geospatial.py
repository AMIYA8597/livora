"""
Unit and Integration Tests for Geospatial Distance, PostGIS Radius Search,
Coordinate Fuzzing, and Flatmate Search.
"""
from uuid import uuid4
from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.infrastructure.geospatial import haversine_distance, compute_bounding_box, fuzz_coordinates
from app.modules.search.schemas import PropertySearchFilter, FlatmateSearchFilter
from app.modules.search.service import SearchService
from app.modules.properties.models import Property
from app.modules.profiles.models import Profile
from app.modules.users.models import User

def test_haversine_distance_calculations():
    """Verify haversine distance gives accurate km distance between Indian coordinates."""
    # MG Road Bengaluru: 12.9756, 77.6066
    # Koramangala 4th Block: 12.9352, 77.6245
    dist = haversine_distance(12.9756, 77.6066, 12.9352, 77.6245)
    assert 4.0 <= dist <= 6.0

    # Identical coordinate check
    assert haversine_distance(12.9756, 77.6066, 12.9756, 77.6066) == 0.0

def test_coordinate_fuzzing_for_privacy():
    """Verify coordinate fuzzing truncates exact residential lat/lon."""
    raw_lat, raw_lng = 12.9715987, 77.5945621
    fuzzed_lat, fuzzed_lng = fuzz_coordinates(raw_lat, raw_lng, precision_decimals=2)
    assert fuzzed_lat == 12.97
    assert fuzzed_lng == 77.59

def test_bounding_box_computation():
    """Verify bounding box calculation covers requested radius."""
    min_lat, max_lat, min_lon, max_lon = compute_bounding_box(12.9716, 77.5946, radius_km=10.0)
    assert min_lat < 12.9716 < max_lat
    assert min_lon < 77.5946 < max_lon

@pytest.mark.asyncio
async def test_property_search_with_radius_and_fuzzing():
    """Properties are filtered by distance radius and unauthenticated viewers receive fuzzed coordinates."""
    mock_db = AsyncMock()
    service = SearchService(mock_db)

    # Prop 1: In Koramangala (~5km from MG Road)
    prop1 = Property(
        id=uuid4(),
        owner_id=uuid4(),
        title="2BHK Koramangala",
        description="Spacious flat",
        property_category="apartment",
        configuration="2BHK",
        address_display="Koramangala 4th Block",
        city="Bengaluru",
        postal_code="560034",
        monthly_rent=Decimal("30000.00"),
        security_deposit=Decimal("90000.00"),
        total_bedrooms=2,
        total_bathrooms=2,
        max_capacity=3,
        current_occupants=0,
        furnishing_status="semi_furnished",
        is_active=True,
        listing_status="published",
    )
    # Prop 2: In Whitefield (~18km from MG Road)
    prop2 = Property(
        id=uuid4(),
        owner_id=uuid4(),
        title="3BHK Whitefield",
        description="Luxury apartment",
        property_category="apartment",
        configuration="3BHK",
        address_display="Whitefield Main Road",
        city="Bengaluru",
        postal_code="560066",
        monthly_rent=Decimal("45000.00"),
        security_deposit=Decimal("150000.00"),
        total_bedrooms=3,
        total_bathrooms=3,
        max_capacity=4,
        current_occupants=0,
        furnishing_status="fully_furnished",
        is_active=True,
        listing_status="published",
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [prop1, prop2]
    mock_db.execute.return_value = mock_res

    # Search with 10km radius from MG Road (12.9756, 77.6066)
    filters = PropertySearchFilter(
        latitude=12.9756,
        longitude=77.6066,
        radius_km=10.0,
        city="Bengaluru",
    )

    # Unauthenticated visitor:
    results = await service.search_properties(filters, is_authenticated_viewer=False)
    assert len(results) >= 1
    # Check that coordinate fuzzing was applied
    assert results[0].is_fuzzed_location is True
    assert round(results[0].latitude, 2) == results[0].latitude
    assert results[0].currency == "INR"

@pytest.mark.asyncio
async def test_flatmate_discovery_search():
    """Flatmates are filtered by locality interest, budget overlap, and lifestyle habits."""
    mock_db = AsyncMock()
    service = SearchService(mock_db)

    user1 = User(id=uuid4(), email="seeker1@example.com", full_name="Aakash Nair", is_active=True, is_verified=True)
    prof1 = Profile(
        id=uuid4(),
        user_id=user1.id,
        display_name="Aakash Nair",
        occupation="Data Scientist",
        budget_min=15000,
        budget_max=25000,
        preferred_locations=["Indiranagar", "Koramangala"],
        lifestyle_traits={"sleep_schedule": "early_bird", "diet": "pure_veg", "smoking": "never"}
    )

    user2 = User(id=uuid4(), email="seeker2@example.com", full_name="Varun Mehta", is_active=True, is_verified=False)
    prof2 = Profile(
        id=uuid4(),
        user_id=user2.id,
        display_name="Varun Mehta",
        occupation="Graphic Designer",
        budget_min=30000,
        budget_max=45000,
        preferred_locations=["Whitefield"],
        lifestyle_traits={"sleep_schedule": "night_owl", "diet": "non_veg", "smoking": "allowed"}
    )

    mock_res = MagicMock()
    mock_res.all.return_value = [(prof1, user1), (prof2, user2)]
    mock_db.execute.return_value = mock_res

    # Search for flatmate in Indiranagar with budget max 20000 and pure_veg diet
    filters = FlatmateSearchFilter(
        locality="Indiranagar",
        max_budget=20000,
        diet_preference="pure_veg"
    )

    results = await service.search_flatmates(filters)
    assert len(results) == 1
    assert results[0].display_name == "Aakash Nair"
    assert results[0].occupation == "Data Scientist"
    assert "Indiranagar" in results[0].preferred_locations
