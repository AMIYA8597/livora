"""Schema-owner sessions for the few tests that must create roles or inspect grants.

The rest of the suite runs as a least-privilege login (see conftest.py).
"""
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def owner_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(os.environ["MIGRATION_DATABASE_URL"], poolclass=NullPool)
    return async_sessionmaker(bind=engine, expire_on_commit=False)
