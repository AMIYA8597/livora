"""
Unit and Integration Tests for Geospatial Distance, PostGIS Radius Search,
Coordinate Fuzzing, and Flatmate Search.
"""
from uuid import uuid4
from decimal import Decimal
from datetime import date
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

# --- Real PostGIS radius search (no mocks) ---------------------------------------------

MG_ROAD = (12.9756, 77.6066)  # (lat, lng)
POINTS = {
    "koramangala": (12.9352, 77.6245),  # ~5 km from MG Road
    "whitefield": (12.9698, 77.7500),   # ~15.5 km
    "mumbai": (19.0760, 72.8777),       # ~840 km
}


@pytest.fixture
async def geo_listings():
    from geoalchemy2.elements import WKTElement
    from sqlalchemy import delete
    from app.core.database import AsyncSessionLocal

    city = f"Geotest-{uuid4().hex[:8]}"  # isolates these rows from anything else in the test DB
    async with AsyncSessionLocal() as session:
        owner = User(id=uuid4(), email=f"geo-{uuid4().hex[:8]}@example.test", hashed_password="x", full_name="Geo Owner")
        session.add(owner)
        await session.flush()
        for name, (lat, lng) in POINTS.items():
            session.add(Property(
                id=uuid4(), owner_id=owner.id, title=f"Flat in {name}", description="test",
                location=WKTElement(f"POINT({lng} {lat})", srid=4326),
                address_display=name, address_exact=f"1 {name} street", city=city, postal_code="560001",
                monthly_rent=Decimal("30000.00"), is_active=True, listing_status="published",
                available_from=date.today(),
            ))
        owner_id = owner.id
        await session.commit()
        yield session, city
        await session.rollback()
        await session.execute(delete(User).where(User.id == owner_id))
        await session.commit()


async def _search(session, city, **kw):
    filters = PropertySearchFilter(latitude=MG_ROAD[0], longitude=MG_ROAD[1], city=city, **kw)
    return await SearchService(session).search_properties(filters, is_authenticated_viewer=False)


async def test_radius_search_excludes_far_listings(geo_listings):
    session, city = geo_listings
    results = await _search(session, city, radius_km=10.0)
    assert [r.address_display for r in results] == ["koramangala"]
    assert 4.0 <= results[0].distance_km <= 6.0


async def test_radius_search_orders_by_distance_with_real_coordinates(geo_listings):
    session, city = geo_listings
    results = await _search(session, city, radius_km=20.0)
    assert [r.address_display for r in results] == ["koramangala", "whitefield"]
    assert 14.0 <= results[1].distance_km <= 17.0
    # Regression: coordinates used to come back as one hardcoded point for every listing.
    assert results[0].latitude != results[1].latitude or results[0].longitude != results[1].longitude
    # Privacy: public results are fuzzed to 2 decimals.
    for r in results:
        assert r.is_fuzzed_location is True
        assert round(r.latitude, 2) == r.latitude


async def test_radius_filter_applies_before_pagination(geo_listings):
    """Regression: LIMIT/OFFSET used to run before the radius filter, so pages were wrong."""
    session, city = geo_listings
    page2 = await _search(session, city, radius_km=20.0, limit=1, offset=1)
    assert [r.address_display for r in page2] == ["whitefield"]


async def test_location_geography_index_is_usable(geo_listings):
    from sqlalchemy import text

    session, _ = geo_listings
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = " | ".join(
        row[0] for row in (await session.execute(text(
            "EXPLAIN SELECT id FROM properties WHERE ST_DWithin(properties.location::geography, "
            "ST_SetSRID(ST_MakePoint(77.6066, 12.9756), 4326)::geography, 10000)"
        ))).all()
    )
    await session.rollback()
    assert "ix_properties_location_geog" in plan


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
