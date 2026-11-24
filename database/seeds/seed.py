"""
Flatmate Platform - development seed data (ORM-based, idempotent).

Schema comes ONLY from Alembic (`cd apps/api && alembic upgrade head`). This script never runs
raw DDL; it inserts data through the application's own SQLAlchemy models and helpers
(password hashing, lifestyle vectors), so it cannot drift from the schema.

    cd apps/api
    alembic upgrade head
    python ../../database/seeds/seed.py              # local databases only
    python ../../database/seeds/seed.py --allow-remote   # e.g. a staging project (never production)

All rows use deterministic UUIDs (uuid5), so re-running updates in place instead of duplicating.

Dev login for every seeded account: the password in SEED_PASSWORD below (local/dev data only).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

API_ROOT = Path(__file__).resolve().parents[2] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from geoalchemy2.elements import WKTElement  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.modules.locations.models import City, Country, Locality, State  # noqa: E402
from app.modules.profiles.models import Profile  # noqa: E402
from app.modules.profiles.schemas import LifestyleTraitsSchema  # noqa: E402
from app.modules.profiles.service import compute_lifestyle_vector  # noqa: E402
from app.modules.properties.models import Property, PropertyAmenity  # noqa: E402
from app.modules.users.models import User, UserPrivacySetting, UserRole  # noqa: E402

SEED_PASSWORD = "FlatmateDev!2026"  # local development accounts only
NAMESPACE = uuid.UUID("6f1c2d4e-0b7a-4c1e-9a55-f1a7c0de5eed")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "postgres-test"}


def sid(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def point(lat: float, lng: float) -> WKTElement:
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


# --- Reference geography (real coordinates) --------------------------------------------
STATES = {"KA": "Karnataka", "MH": "Maharashtra", "TS": "Telangana"}
CITIES = {
    # slug: (name, state, lat, lng)
    "bengaluru": ("Bengaluru", "KA", 12.9716, 77.5946),
    "mumbai": ("Mumbai", "MH", 19.0760, 72.8777),
    "pune": ("Pune", "MH", 18.5204, 73.8567),
    "hyderabad": ("Hyderabad", "TS", 17.3850, 78.4867),
}
LOCALITIES = {
    # key: (city slug, name, pin, lat, lng)
    "hsr": ("bengaluru", "HSR Layout", "560102", 12.9121, 77.6446),
    "koramangala": ("bengaluru", "Koramangala", "560034", 12.9352, 77.6245),
    "indiranagar": ("bengaluru", "Indiranagar", "560038", 12.9784, 77.6408),
    "whitefield": ("bengaluru", "Whitefield", "560066", 12.9698, 77.7500),
    "andheri": ("mumbai", "Andheri West", "400053", 19.1364, 72.8296),
    "powai": ("mumbai", "Powai", "400076", 19.1176, 72.9060),
    "baner": ("pune", "Baner", "411045", 18.5590, 73.7868),
    "hinjewadi": ("pune", "Hinjewadi", "411057", 18.5913, 73.7389),
    "gachibowli": ("hyderabad", "Gachibowli", "500032", 17.4401, 78.3489),
    "madhapur": ("hyderabad", "Madhapur", "500081", 17.4483, 78.3915),
}

# --- People ----------------------------------------------------------------------------
SEEKERS = [
    # key, name, occupation, budget, localities, traits
    ("priya", "Priya Sharma", "Software Engineer", (12000, 20000), ["HSR Layout", "Koramangala"],
     dict(sleep_schedule="early_bird", cleanliness_level=5, social_battery="introverted", work_arrangement="hybrid",
          diet="vegetarian", smoking="never", pets="cats_ok", guests_policy="rarely")),
    ("arjun", "Arjun Mehta", "Product Designer", (15000, 25000), ["Indiranagar", "Koramangala"],
     dict(sleep_schedule="night_owl", cleanliness_level=3, social_battery="extroverted", work_arrangement="remote",
          diet="omnivore", smoking="outside_only", pets="loves_pets", guests_policy="frequent")),
    ("ananya", "Ananya Iyer", "Data Analyst", (10000, 18000), ["HSR Layout", "Whitefield"],
     dict(sleep_schedule="early_bird", cleanliness_level=4, social_battery="moderate", work_arrangement="on_site",
          diet="vegetarian", smoking="never", pets="no_pets", guests_policy="occasional_weekends")),
    ("rohan", "Rohan Kulkarni", "Consultant", (20000, 35000), ["Powai", "Andheri West"],
     dict(sleep_schedule="flexible", cleanliness_level=4, social_battery="balanced", work_arrangement="hybrid",
          diet="omnivore", smoking="never", pets="dogs_ok", guests_policy="occasional_weekends")),
    ("sneha", "Sneha Patil", "UX Researcher", (14000, 22000), ["Baner", "Hinjewadi"],
     dict(sleep_schedule="early_bird", cleanliness_level=5, social_battery="moderate", work_arrangement="hybrid",
          diet="vegan", smoking="never", pets="has_cat", guests_policy="rarely")),
    ("vikram", "Vikram Reddy", "Backend Engineer", (15000, 28000), ["Gachibowli", "Madhapur"],
     dict(sleep_schedule="night_owl", cleanliness_level=3, social_battery="introverted", work_arrangement="remote",
          diet="omnivore", smoking="never", pets="cats_ok", guests_policy="rarely")),
    ("meera", "Meera Nair", "Doctor (Resident)", (12000, 20000), ["Koramangala", "Indiranagar"],
     dict(sleep_schedule="flexible", cleanliness_level=5, social_battery="introverted", work_arrangement="on_site",
          diet="pescatarian", smoking="never", pets="no_pets", guests_policy="rarely")),
    ("kabir", "Kabir Singh", "Sales Manager", (18000, 30000), ["Andheri West", "Powai"],
     dict(sleep_schedule="night_owl", cleanliness_level=2, social_battery="extroverted", work_arrangement="on_site",
          diet="omnivore", smoking="allowed", pets="dogs_ok", guests_policy="frequent")),
]
OWNERS = [("owner_ravi", "Ravi Kumar"), ("owner_fatima", "Fatima Shaikh")]

# --- Listings: locality key, owner, title, config, rent, offsets (deg) ------------------
LISTINGS = [
    ("hsr", "owner_ravi", "Sunlit 2BHK near HSR BDA Complex", "2BHK", 32000, (0.002, -0.001)),
    ("hsr", "owner_ravi", "Private room in 3BHK, HSR Sector 6", "3BHK", 14000, (-0.004, 0.003)),
    ("koramangala", "owner_ravi", "Furnished 1BHK off 80 Feet Road", "1BHK", 26000, (0.001, 0.002)),
    ("indiranagar", "owner_fatima", "Shared flat near 100 Feet Road", "3BHK", 16000, (-0.002, -0.002)),
    ("whitefield", "owner_fatima", "Gated-society 2BHK near ITPL", "2BHK", 24000, (0.003, 0.001)),
    ("andheri", "owner_fatima", "Room in 2BHK, Lokhandwala", "2BHK", 22000, (0.001, -0.002)),
    ("powai", "owner_fatima", "Lake-view 2BHK in Hiranandani", "2BHK", 48000, (-0.002, 0.001)),
    ("baner", "owner_ravi", "Co-living room, Baner High Street", "co_living", 13000, (0.002, 0.002)),
    ("hinjewadi", "owner_ravi", "1RK near Phase 1 IT Park", "1RK", 11000, (-0.001, 0.003)),
    ("gachibowli", "owner_fatima", "3BHK share near DLF Cybercity", "3BHK", 15000, (0.002, -0.003)),
    ("madhapur", "owner_fatima", "Studio near Hitech City Metro", "studio", 19000, (-0.003, 0.001)),
]
AMENITIES = ["wifi", "power_backup", "ro_water", "geyser", "security_24x7", "washing_machine"]


def _guard(allow_remote: bool) -> None:
    env = (settings.ENVIRONMENT or "").lower()
    if env in {"production", "prod"}:
        raise SystemExit("Refusing to seed: ENVIRONMENT is production.")
    host = urlparse(settings.DATABASE_URL.replace("+asyncpg", "")).hostname
    if host not in LOCAL_HOSTS and not allow_remote:
        raise SystemExit(f"Refusing to seed non-local database host '{host}'. Pass --allow-remote for staging.")


async def seed(allow_remote: bool = False) -> dict:
    _guard(allow_remote)
    password_hash = get_password_hash(SEED_PASSWORD)
    today = date.today()

    async with AsyncSessionLocal() as s:
        country = await s.merge(Country(id=sid("country:IND"), code="IND", name="India"))
        states = {code: await s.merge(State(id=sid(f"state:{code}"), country_id=country.id, name=name, code=code))
                  for code, name in STATES.items()}
        cities = {}
        for slug, (name, st, lat, lng) in CITIES.items():
            cities[slug] = await s.merge(City(id=sid(f"city:{slug}"), state_id=states[st].id, name=name, slug=slug,
                                              tier=1, center_location=point(lat, lng)))
        for key, (city_slug, name, pin, lat, lng) in LOCALITIES.items():
            await s.merge(Locality(id=sid(f"locality:{key}"), city_id=cities[city_slug].id, name=name,
                                   postal_code=pin, center_location=point(lat, lng)))

        async def add_user(key: str, name: str, role: str) -> uuid.UUID:
            uid = sid(f"user:{key}")
            await s.merge(User(id=uid, email=f"{key}@seed.example.com", hashed_password=password_hash,
                               full_name=name, role=role, is_active=True, is_verified=True))
            await s.merge(UserRole(id=sid(f"role:{key}:{role}"), user_id=uid, role=role, is_verified=True))
            await s.merge(UserPrivacySetting(id=sid(f"privacy:{key}"), user_id=uid, profile_visibility="public"))
            return uid

        await add_user("admin", "Platform Admin", "admin")
        owner_ids = {key: await add_user(key, name, "owner") for key, name in OWNERS}

        for key, name, occupation, (bmin, bmax), locs, traits in SEEKERS:
            uid = await add_user(key, name, "seeker")
            trait_model = LifestyleTraitsSchema(**traits)
            await s.merge(Profile(
                id=sid(f"profile:{key}"), user_id=uid, display_name=name, occupation=occupation,
                bio=f"{occupation} looking for a compatible flatmate.", budget_min=bmin, budget_max=bmax,
                move_in_date=today + timedelta(days=30), preferred_locations=locs,
                lifestyle_traits=trait_model.model_dump(), lifestyle_vector=compute_lifestyle_vector(trait_model),
            ))
        for key, name in [("admin", "Platform Admin"), *OWNERS]:
            await s.merge(Profile(id=sid(f"profile:{key}"), user_id=sid(f"user:{key}"), display_name=name,
                                  lifestyle_vector=[0.0] * settings.VECTOR_EMBEDDING_DIM,
                                  lifestyle_traits={}, preferred_locations=[]))

        for i, (loc_key, owner_key, title, config, rent, (dlat, dlng)) in enumerate(LISTINGS):
            city_slug, loc_name, pin, lat, lng = LOCALITIES[loc_key]
            pid = sid(f"property:{i}")
            await s.merge(Property(
                id=pid, owner_id=owner_ids[owner_key], title=title,
                description=f"{title}. Well-connected, verified listing in {loc_name}.",
                property_category="co_living" if config == "co_living" else "apartment",
                configuration="1RK" if config == "co_living" else config,
                location=point(lat + dlat, lng + dlng),
                address_display=f"{loc_name}, {CITIES[city_slug][0]}",
                address_exact=f"Flat {101 + i}, Seed Residency, {loc_name}",
                city=CITIES[city_slug][0], state=STATES[CITIES[city_slug][1]], postal_code=pin,
                monthly_rent=Decimal(rent), security_deposit=Decimal(rent * 2),
                available_from=today + timedelta(days=7 * (i % 4)),
                furnishing_status="fully_furnished" if i % 2 == 0 else "semi_furnished",
                listing_status="published", is_active=True, is_verified=True, images=[],
            ))
            for amenity in AMENITIES[: 3 + i % 4]:
                await s.merge(PropertyAmenity(id=sid(f"amenity:{i}:{amenity}"), property_id=pid, amenity_key=amenity))

        await s.commit()

    return {"cities": len(CITIES), "localities": len(LOCALITIES),
            "users": 1 + len(OWNERS) + len(SEEKERS), "properties": len(LISTINGS)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--allow-remote", action="store_true", help="allow a non-local (staging) database")
    args = parser.parse_args()
    counts = asyncio.run(seed(allow_remote=args.allow_remote))
    print("Seeded:", ", ".join(f"{v} {k}" for k, v in counts.items()))


if __name__ == "__main__":
    os.environ.setdefault("ENVIRONMENT", "development")
    main()
