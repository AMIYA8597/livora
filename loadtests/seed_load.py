"""
Load-test data: members (seekers), owners and published listings across the catalogue cities,
plus a tokens file Locust reads (loadtests/.tokens.json, git-ignored).

    cd apps/api
    DATABASE_URL=postgresql+asyncpg://.../flatmate_load SECRET_KEY=... \
        python ../../loadtests/seed_load.py --members 2000 --listings 3000
    python ../../loadtests/seed_load.py --cleanup        # remove everything it created

Runs with the API's own settings (DATABASE_URL, SECRET_KEY), so the tokens it writes are valid for
an API started with the same SECRET_KEY. Refuses any database that isn't on this machine unless
the host is named with --allow-host (a staging database, never production). Every account it
makes uses @loadtest.example.com (RFC 2606), which --cleanup deletes (listings go with them).

Tokens are minted directly (one sign-in per virtual user would hit the sign-in rate limit, which
is per IP, long before the API's capacity); the SignIn user class in the locustfile still
exercises real sign-ins at a rate the limit allows.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import secrets
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

API_DIR = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_DIR))

DOMAIN = "loadtest.example.com"  # reserved for examples (RFC 2606); passes email validation
TOKENS = Path(__file__).with_name(".tokens.json")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

CATEGORIES = ["apartment", "pg", "co_living", "independent_house", "hostel"]
CONFIGS = ["1RK", "1BHK", "2BHK", "3BHK", "studio"]
FURNISHING = ["fully_furnished", "semi_furnished", "unfurnished"]
WORDS = ["quiet", "sunny", "spacious", "metro", "furnished", "balcony", "gated", "near IT park",
         "wifi", "parking", "female only", "vegetarian kitchen", "pet friendly", "lake view"]


def guard(database_url: str, allow_host: str | None) -> None:
    host = urlparse(database_url.replace("+asyncpg", "")).hostname or ""
    if host in LOCAL_HOSTS:
        return
    if allow_host and host == allow_host:
        if "prod" in host.lower():
            sys.exit("refusing a database whose host looks like production")
        return
    sys.exit(f"refusing database host {host!r}: pass --allow-host {host} if it is a staging database")


async def cleanup() -> None:
    from sqlalchemy import delete, select

    from app.core.database import AsyncSessionLocal
    from app.modules.users.models import User

    async with AsyncSessionLocal() as s:
        ids = (await s.execute(select(User.id).where(User.email.like(f"%@{DOMAIN}")))).scalars().all()
        for i in range(0, len(ids), 500):
            await s.execute(delete(User).where(User.id.in_(ids[i:i + 500])))
        await s.commit()
    TOKENS.unlink(missing_ok=True)
    print(f"removed {len(ids)} load-test accounts (and their listings)")


async def seed(members: int, owners: int, listings: int, token_hours: int) -> None:
    from geoalchemy2 import WKTElement
    from sqlalchemy import func, select

    from app.core.database import AsyncSessionLocal
    from app.core.security import create_access_token, get_password_hash
    from app.modules.locations.models import City, State
    from app.modules.properties.models import Property
    from app.modules.users.models import User, UserRole

    rng = random.Random(42)
    run = uuid.uuid4().hex[:6]
    password = secrets.token_urlsafe(18)
    hashed = get_password_hash(password)  # once: bcrypt is deliberately slow

    async with AsyncSessionLocal() as s:
        cities = (await s.execute(
            select(City.name, State.name, func.ST_Y(City.center_location), func.ST_X(City.center_location))
            .join(State, State.id == City.state_id)
            .where(City.is_active.is_(True), City.center_location.is_not(None))
        )).all()
    if not cities:
        sys.exit("no cities in the catalogue: run the migrations first")

    member_rows, owner_ids = [], []
    async with AsyncSessionLocal() as s:
        for i in range(members):
            uid = uuid.uuid4()
            email = f"member-{run}-{i}@{DOMAIN}"
            s.add(User(id=uid, email=email, hashed_password=hashed, full_name=f"Load Member {i}", role="seeker"))
            member_rows.append((uid, email))
        for i in range(owners):
            uid = uuid.uuid4()
            s.add(User(id=uid, email=f"owner-{run}-{i}@{DOMAIN}", hashed_password=hashed,
                       full_name=f"Load Owner {i}", role="owner"))
            owner_ids.append(uid)
        await s.flush()
        for uid in owner_ids:
            s.add(UserRole(user_id=uid, role="owner", is_verified=True))
        await s.commit()

    listing_cities: dict[str, int] = {}
    for start in range(0, listings, 500):
        async with AsyncSessionLocal() as s:
            for i in range(start, min(listings, start + 500)):
                city, state, lat, lng = cities[i % len(cities)]
                listing_cities[city] = listing_cities.get(city, 0) + 1
                plat, plng = lat + rng.uniform(-0.08, 0.08), lng + rng.uniform(-0.08, 0.08)
                words = " ".join(rng.sample(WORDS, 3))
                s.add(Property(
                    owner_id=owner_ids[i % len(owner_ids)],
                    title=f"{rng.choice(CONFIGS)} {words} in {city}"[:255],
                    description=f"A {words} home in {city}, {state}. Load-test listing {i}.",
                    property_category=rng.choice(CATEGORIES),
                    configuration=rng.choice(CONFIGS),
                    location=WKTElement(f"POINT({plng} {plat})", srid=4326),
                    address_display=f"Sector {rng.randint(1, 40)}, {city}",
                    address_exact=f"Flat {rng.randint(1, 999)}",
                    city=city, state=state, postal_code=f"{rng.randint(110001, 855999)}",
                    monthly_rent=Decimal(rng.randrange(4000, 60000, 500)),
                    security_deposit=Decimal(rng.randrange(10000, 150000, 5000)),
                    total_bedrooms=rng.randint(1, 4), total_bathrooms=rng.randint(1, 3),
                    max_capacity=rng.randint(1, 6), available_from=date.today() + timedelta(days=rng.randint(0, 60)),
                    furnishing_status=rng.choice(FURNISHING), listing_status="published", is_active=True,
                    is_verified=True, images=[],
                ))
            await s.commit()

    expires = timedelta(hours=token_hours)
    TOKENS.write_text(json.dumps({
        "password": password,
        "cities": sorted(listing_cities, key=listing_cities.get, reverse=True),
        "members": [
            {"email": email, "token": create_access_token(subject=str(uid), roles=["seeker"], expires_delta=expires)}
            for uid, email in member_rows
        ],
    }), encoding="utf-8")
    os.chmod(TOKENS, 0o600)
    print(f"created {members} members, {owners} owners, {listings} listings in {len(listing_cities)} cities;"
          f" tokens valid {token_hours}h in {TOKENS.name}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--members", type=int, default=1000)
    p.add_argument("--owners", type=int, default=200)
    p.add_argument("--listings", type=int, default=2000)
    p.add_argument("--token-hours", type=int, default=6)
    p.add_argument("--allow-host", help="a non-local (staging) database host to allow")
    p.add_argument("--cleanup", action="store_true", help="delete everything this script created")
    args = p.parse_args()

    from app.core.config import settings

    guard(settings.DATABASE_URL, args.allow_host)
    if args.cleanup:
        asyncio.run(cleanup())
    else:
        if args.members < 1 or args.owners < 1 or args.listings < 0:
            sys.exit("need at least one member and one owner")
        asyncio.run(seed(args.members, args.owners, args.listings, args.token_hours))


if __name__ == "__main__":
    main()
