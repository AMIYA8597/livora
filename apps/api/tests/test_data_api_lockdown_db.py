"""
Supabase Data API lockdown (migration 005), verified on a real database.

Supabase grants `anon`/`authenticated` broad privileges on `public` by default. The test
recreates that state inside a transaction (roles + grants), runs the migration's SQL, proves
the API roles are locked out, then rolls everything back.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from tests.db_owner import owner_session_factory

AsyncSessionLocal = owner_session_factory()  # creating roles needs the schema owner

_MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "005_lockdown_data_api.py"
_spec = importlib.util.spec_from_file_location("migration_005", _MIGRATION)
assert _spec and _spec.loader
migration_005 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_005)

SENSITIVE_TABLES = ["users", "profiles", "messages", "payments", "alembic_version"]


async def test_every_application_table_has_rls_enabled():
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(text("""
            SELECT c.relname
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relrowsecurity
              AND NOT EXISTS (SELECT 1 FROM pg_depend d
                              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
        """))).scalars().all()
    assert rows == [], f"Tables without RLS (exposed via Supabase Data API): {rows}"


@pytest.mark.parametrize("api_role", ["anon", "authenticated"])
async def test_api_roles_cannot_read_after_lockdown(api_role):
    async with AsyncSessionLocal() as session:
        conn = await session.connection()
        try:
            # Recreate Supabase's default exposure inside this transaction.
            await conn.execute(text(f"""
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{api_role}') THEN
                        CREATE ROLE {api_role} NOLOGIN;
                    END IF;
                END $$;
            """))
            await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {api_role}"))
            await conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {api_role}"))

            await conn.execute(text(migration_005.LOCKDOWN_SQL))

            for table in SENSITIVE_TABLES:
                await conn.execute(text("SAVEPOINT probe"))
                await conn.execute(text(f"SET LOCAL ROLE {api_role}"))
                with pytest.raises(Exception) as exc:
                    await conn.execute(text(f"SELECT 1 FROM public.{table} LIMIT 1"))
                assert "permission denied" in str(exc.value).lower(), table
                await conn.execute(text("ROLLBACK TO SAVEPOINT probe"))
        finally:
            await session.rollback()
