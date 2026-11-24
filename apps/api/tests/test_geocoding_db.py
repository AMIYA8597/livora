"""
Placing new listings on the map (OpenStreetMap Nominatim) against a real database, with the
network faked: only public fields are looked up, wrong matches are ignored, the job is
idempotent, and Nominatim's usage rules (User-Agent, India only, back off when busy) hold.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from geoalchemy2.shape import to_shape
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.modules.locations import geocoding
from app.modules.locations.geocoding import (
    GEOCODE_EVENT, GeocoderUnavailable, NominatimGeocoder, geocode_listing, precision_for_new_listing,
)
from app.modules.messaging.models import OutboxEvent
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.users.models import User
from app.workers.outbox import HANDLERS

LEH = (34.1526, 77.5771)  # the catalogue's centre for Leh
SECRET_FLAT = "Flat 9, Hidden Lane"


def _listing(lat: float, lng: float) -> PropertyCreate:
    return PropertyCreate(
        title="Guest room near the market", description="Warm room.", property_category="apartment",
        configuration="1BHK", latitude=lat, longitude=lng, address_display="Changspa, Leh",
        address_exact=SECRET_FLAT, city="Leh", state="Ladakh", postal_code="194101",
        monthly_rent=Decimal("9000"), max_capacity=1, available_from=date.today(), currency="INR",
    )


class FakeGeocoder:
    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    async def search(self, params):
        self.asked.append(params)
        return self.answers.pop(0) if self.answers else None


@pytest.fixture
async def owner():
    uid = uuid4()
    async with AsyncSessionLocal() as s:
        s.add(User(id=uid, email=f"geo-{uid.hex[:8]}@example.com", hashed_password="x", full_name="Geo Owner", role="owner"))
        await s.commit()
    yield uid
    async with AsyncSessionLocal() as s:
        ids = select(Property.id).where(Property.owner_id == uid)
        prop_ids = [str(i) for i in (await s.execute(ids)).scalars().all()]
        if prop_ids:
            await s.execute(delete(OutboxEvent).where(OutboxEvent.payload["property_id"].astext.in_(prop_ids)))
        await s.execute(delete(Property).where(Property.owner_id == uid))
        await s.execute(delete(User).where(User.id == uid))
        await s.commit()


async def _create(owner, lat, lng):
    async with AsyncSessionLocal() as s:
        return (await PropertyService(s).create(owner, _listing(lat, lng)))["id"]


async def _row(pid):
    async with AsyncSessionLocal() as s:
        prop = await s.get(Property, pid)
        point = to_shape(prop.location)
        jobs = (await s.execute(select(OutboxEvent).where(
            OutboxEvent.event_type == GEOCODE_EVENT, OutboxEvent.payload["property_id"].astext == str(pid)
        ))).scalars().all()
        return prop.location_precision, (point.y, point.x), jobs


def test_a_point_at_the_city_centre_is_a_placeholder():
    assert precision_for_new_listing(*LEH, LEH) == "city"
    assert precision_for_new_listing(34.155, 77.575, LEH) == "city"  # within 1 km
    assert precision_for_new_listing(34.17, 77.60, LEH) == "owner"
    assert precision_for_new_listing(34.17, 77.60, None) == "owner"
    assert "listing.geocode" in HANDLERS


async def test_a_listing_at_the_city_centre_is_queued_and_placed_from_public_fields(owner):
    pid = await _create(owner, *LEH)
    precision, _, jobs = await _row(pid)
    assert precision == "city" and len(jobs) == 1
    assert jobs[0].payload == {"property_id": str(pid)}  # no address in the job

    fake = FakeGeocoder([(34.1642, 77.5741)])  # Changspa
    result = await geocode_listing(AsyncSessionLocal, pid, geocoder=fake)
    assert result == {"property_id": str(pid), "outcome": "locality"}
    precision, point, _ = await _row(pid)
    assert precision == "locality" and point == pytest.approx((34.1642, 77.5741), abs=1e-6)
    assert fake.asked[0] == {"q": "Changspa, Leh, Ladakh 194101"}
    assert all(SECRET_FLAT not in str(p) for p in fake.asked)

    again = FakeGeocoder([(30.0, 70.0)])
    assert (await geocode_listing(AsyncSessionLocal, pid, geocoder=again))["outcome"] == "skipped"
    assert again.asked == []  # idempotent: an at-least-once retry costs nothing


async def test_an_owners_own_pin_is_kept_and_not_looked_up(owner):
    pid = await _create(owner, 34.17, 77.60)
    precision, point, jobs = await _row(pid)
    assert precision == "owner" and jobs == [] and point == pytest.approx((34.17, 77.60))
    assert (await geocode_listing(AsyncSessionLocal, pid, geocoder=FakeGeocoder([])))["outcome"] == "skipped"


async def test_matches_far_from_the_city_are_ignored_and_the_pin_code_is_the_fallback(owner):
    pid = await _create(owner, *LEH)
    # 1st: a "Changspa" somewhere else in India; 2nd: nothing; 3rd: the PIN code's area.
    fake = FakeGeocoder([(28.61, 77.21), None, (34.1600, 77.5800)])
    assert (await geocode_listing(AsyncSessionLocal, pid, geocoder=fake))["outcome"] == "postcode"
    assert [list(p) for p in fake.asked] == [["q"], ["q"], ["postalcode", "country"]]
    precision, point, _ = await _row(pid)
    assert precision == "postcode" and point == pytest.approx((34.16, 77.58))


async def test_nothing_found_leaves_the_city_centre(owner):
    pid = await _create(owner, *LEH)
    assert (await geocode_listing(AsyncSessionLocal, pid, geocoder=FakeGeocoder([])))["outcome"] == "not_found"
    precision, point, _ = await _row(pid)
    assert precision == "city" and point == pytest.approx(LEH)


async def test_switched_off_without_a_geocoder(owner):
    pid = await _create(owner, *LEH)
    assert (await geocode_listing(AsyncSessionLocal, pid))["outcome"] == "disabled"  # GEOCODER=off in tests


async def test_nominatim_requests_follow_the_usage_policy(monkeypatch):
    monkeypatch.setattr(geocoding, "MIN_INTERVAL_SECONDS", 0)
    seen = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        q = request.url.params.get("q", "")
        if "busy" in q:
            return httpx.Response(429)
        if "nowhere" in q:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{"lat": "34.1642", "lon": "77.5741", "display_name": "Changspa"}])

    nominatim = NominatimGeocoder("https://nominatim.example/", "Flatmate/1.0 (test)", email="ops@example.com",
                                  transport=httpx.MockTransport(answer))
    assert await nominatim.search({"q": "Changspa, Leh"}) == (34.1642, 77.5741)
    assert await nominatim.search({"q": "nowhere"}) is None
    with pytest.raises(GeocoderUnavailable):
        await nominatim.search({"q": "busy"})

    first = seen[0]
    assert first.url.host == "nominatim.example" and first.url.path == "/search"
    assert first.headers["user-agent"] == "Flatmate/1.0 (test)"
    params = dict(first.url.params)
    assert params["countrycodes"] == "in" and params["format"] == "jsonv2" and params["limit"] == "1"
    assert params["email"] == "ops@example.com"


async def test_results_are_cached(monkeypatch):
    monkeypatch.setattr(geocoding, "MIN_INTERVAL_SECONDS", 0)

    class MemoryRedis:
        def __init__(self):
            self.data = {}

        async def get(self, key):
            return self.data.get(key)

        async def set(self, key, value, ex=None, nx=False, px=None):
            if nx and key in self.data:
                return False
            if not key.endswith(":slot"):
                self.data[key] = value
            return True

    calls = []

    def answer(request):
        calls.append(request)
        return httpx.Response(200, json=[{"lat": "34.1642", "lon": "77.5741"}] if "Changspa" in request.url.params["q"] else [])

    nominatim = NominatimGeocoder("https://nominatim.example", "Flatmate/1.0 (test)",
                                  transport=httpx.MockTransport(answer), redis=MemoryRedis())
    for _ in range(3):
        assert await nominatim.search({"q": "Changspa, Leh"}) == (34.1642, 77.5741)
        assert await nominatim.search({"q": " CHANGSPA, LEH "}) == (34.1642, 77.5741)  # same place, same key
        assert await nominatim.search({"q": "nowhere"}) is None  # misses are cached too
    assert len(calls) == 2
