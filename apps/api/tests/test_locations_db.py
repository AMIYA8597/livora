"""
India's location catalogue (migration 016) against a real database: every state and union
territory with its capital, the public lists, and listings saved and found under any city name.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestException
from app.modules.groups.models import Group, GroupMember, GroupWishlistItem
from app.modules.groups.schemas import GroupCreate
from app.modules.groups.service import GroupService
from app.modules.locations.service import LocationService
from app.modules.properties.models import Property
from app.modules.properties.schemas import PropertyCreate
from app.modules.properties.service import PropertyService
from app.modules.users.models import User

API = settings.API_V1_PREFIX

CAPITALS = {
    "AP": "Amaravati", "AR": "Itanagar", "AS": "Dispur", "BR": "Patna", "CG": "Raipur", "GA": "Panaji",
    "GJ": "Gandhinagar", "HR": "Chandigarh", "HP": "Shimla", "JH": "Ranchi", "KA": "Bengaluru",
    "KL": "Thiruvananthapuram", "MP": "Bhopal", "MH": "Mumbai", "MN": "Imphal", "ML": "Shillong",
    "MZ": "Aizawl", "NL": "Kohima", "OD": "Bhubaneswar", "PB": "Chandigarh", "RJ": "Jaipur",
    "SK": "Gangtok", "TN": "Chennai", "TS": "Hyderabad", "TR": "Agartala", "UP": "Lucknow",
    "UK": "Dehradun", "WB": "Kolkata",
    # Union territories
    "AN": "Sri Vijaya Puram", "CH": "Chandigarh", "DD": "Daman", "DL": "New Delhi", "JK": "Srinagar",
    "LA": "Leh", "LD": "Kavaratti", "PY": "Puducherry",
}


async def test_every_state_and_union_territory_has_its_capital(async_client):
    res = await async_client.get(f"{API}/locations/states")
    assert res.status_code == 200
    assert "max-age" in res.headers.get("cache-control", "")
    states = {s["code"]: s for s in res.json()}
    assert {code: s["capital"] for code, s in states.items()} == CAPITALS
    assert sum(s["kind"] == "union_territory" for s in states.values()) == 8
    assert sum(s["kind"] == "state" for s in states.values()) == 28


async def test_the_city_list_has_every_capital_and_the_names_people_search_for(async_client):
    res = await async_client.get(f"{API}/locations/cities")
    assert res.status_code == 200
    cities = {c["slug"]: c for c in res.json()}
    assert set(CAPITALS.values()) <= {c["name"] for c in cities.values()}
    assert {"Pune", "Jammu"} <= {c["name"] for c in cities.values()}  # not capitals, still open
    assert cities["chandigarh"]["is_capital"] and not cities["pune"]["is_capital"]
    blr = cities["bengaluru"]
    assert blr["state"] == "Karnataka" and blr["state_code"] == "KA" and blr["state_kind"] == "state"
    assert "Bangalore" in blr["aliases"]
    assert abs(blr["latitude"] - 12.97) < 0.05 and abs(blr["longitude"] - 77.59) < 0.05
    assert cities["leh"]["state_kind"] == "union_territory"
    for c in cities.values():  # every centre is inside India's bounding box
        assert 6 < c["latitude"] < 37 and 68 < c["longitude"] < 98, c["name"]


@pytest.mark.parametrize("typed, official", [
    ("Bangalore", "Bengaluru"), ("  bengaluru ", "Bengaluru"), ("Port Blair", "Sri Vijaya Puram"),
    ("Delhi NCR", "New Delhi"), ("delhi", "New Delhi"), ("new delhi", "New Delhi"), ("Trivandrum", "Thiruvananthapuram"),
    ("sri vijaya puram", "Sri Vijaya Puram"),
])
async def test_any_name_of_a_city_resolves_to_its_official_name(typed, official):
    async with AsyncSessionLocal() as s:
        assert (await LocationService(s).resolve(typed)).name == official


async def test_unknown_names_do_not_resolve():
    async with AsyncSessionLocal() as s:
        for name in ("", "   ", "Atlantis", "Beng"):
            assert await LocationService(s).resolve(name) is None


def _listing(city: str, title: str) -> PropertyCreate:
    return PropertyCreate(
        title=title, description="Bright room.", property_category="apartment", configuration="1BHK",
        latitude=12.93, longitude=77.62, address_display="Koramangala", address_exact="1 Test St",
        city=city, state="Wrong State", postal_code="560034", monthly_rent=Decimal("15000"),
        max_capacity=1, available_from=date.today(), currency="INR",
    )


async def test_listings_use_the_official_city_and_are_found_by_any_name(async_client):
    owner = uuid4()
    tag = uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        s.add(User(id=owner, email=f"loc-{tag}@example.com", hashed_password="x", full_name="Lata Owner", role="owner"))
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            created = await PropertyService(s).create(owner, _listing("bangalore", f"Catalogue room {tag}"))
        assert created["city"] == "Bengaluru"
        async with AsyncSessionLocal() as s:
            prop = await s.get(Property, created["id"])
            assert prop.city == "Bengaluru" and prop.state == "Karnataka"  # the state comes from the catalogue

        async with AsyncSessionLocal() as s:
            with pytest.raises(BadRequestException) as err:
                await PropertyService(s).create(owner, _listing("Atlantis", f"Nowhere room {tag}"))
        assert err.value.error_code == "UNSUPPORTED_CITY"

        for name in ("Bangalore", "Bengaluru", "Beng"):  # an alias, the name, and a partly typed name
            res = await async_client.get(f"{API}/properties", params={"city": name, "limit": 100})
            assert res.status_code == 200
            assert str(created["id"]) in {p["id"] for p in res.json()}, name
        res = await async_client.get(f"{API}/properties", params={"city": "Mumbai", "limit": 100})
        assert str(created["id"]) not in {p["id"] for p in res.json()}
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Property).where(Property.owner_id == owner))
            await s.execute(delete(User).where(User.id == owner))
            await s.commit()


async def test_groups_save_a_known_city_by_its_official_name_and_keep_others_as_typed():
    creator = uuid4()
    tag = uuid4().hex[:8]
    async with AsyncSessionLocal() as s:
        s.add(User(id=creator, email=f"grp-{tag}@example.com", hashed_password="x", full_name="Gita Seeker", role="seeker"))
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            svc = GroupService(s)
            known = await svc.create(creator, GroupCreate(name=f"Known {tag}", target_budget_total=40000, target_city=" bangalore "))
            other = await svc.create(creator, GroupCreate(name=f"Other {tag}", target_budget_total=40000, target_city=" Whitefield 100% "))
            await s.commit()
        assert known.target_city == "Bengaluru"
        assert other.target_city == "Whitefield 100%"  # groups may aim anywhere; only trimmed

        async with AsyncSessionLocal() as s:
            for typed in ("Bangalore", "BENGALURU"):
                assert known.id in {g.id for g in await GroupService(s).list_groups(typed)}, typed
            found = {g.id for g in await GroupService(s).list_groups("field 100%")}
            assert other.id in found and known.id not in found
            # "%" is a literal character, not a wildcard
            assert other.id not in {g.id for g in await GroupService(s).list_groups("White%100")}
    finally:
        async with AsyncSessionLocal() as s:
            ids = select(Group.id).where(Group.creator_id == creator)
            await s.execute(delete(GroupWishlistItem).where(GroupWishlistItem.group_id.in_(ids)))
            await s.execute(delete(GroupMember).where(GroupMember.group_id.in_(ids)))
            await s.execute(delete(Group).where(Group.creator_id == creator))
            await s.execute(delete(User).where(User.id == creator))
            await s.commit()
