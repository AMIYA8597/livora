"""The dev seed must run against the current Alembic schema and be idempotent.

Regression guard: the previous seeds (01_seed_data.sql, staging_seed.py) referenced columns that
no longer existed and silently rotted.
"""
import importlib.util
from pathlib import Path

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.modules.properties.models import Property
from app.modules.users.models import User

_SEED = Path(__file__).resolve().parents[3] / "database" / "seeds" / "seed.py"
_spec = importlib.util.spec_from_file_location("flatmate_seed", _SEED)
assert _spec and _spec.loader
seed_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_module)


async def _counts():
    async with AsyncSessionLocal() as s:
        users = await s.scalar(select(func.count()).select_from(User).where(User.email.like("%@seed.example.com")))
        props = await s.scalar(select(func.count()).select_from(Property).where(Property.address_exact.like("%Seed Residency%")))
        distinct_points = await s.scalar(
            select(func.count(func.distinct(func.ST_AsText(Property.location))))
            .where(Property.address_exact.like("%Seed Residency%"))
        )
    return users, props, distinct_points


async def test_seed_runs_and_is_idempotent():
    first = await seed_module.seed()
    after_first = await _counts()
    await seed_module.seed()
    after_second = await _counts()

    assert after_first == after_second, "re-running the seed must not duplicate rows"
    assert after_first[0] == first["users"]
    assert after_first[1] == first["properties"]
    assert after_first[2] == first["properties"], "every seeded listing must have its own real location"


async def test_seeded_accounts_can_sign_in(async_client):
    """The seed used an @*.test domain, which the API's email validation rejects as reserved, so no
    seeded account could log in."""
    await seed_module.seed()
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "priya@seed.example.com", "password": seed_module.SEED_PASSWORD})
    assert res.status_code == 200, res.text
