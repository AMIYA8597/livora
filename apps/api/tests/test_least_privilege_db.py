"""
Least-privilege runtime role (migration 007), verified on a real database.

The whole suite runs as `flatmate_api_test`, a login in the `flatmate_app` group role
(see conftest.py). These tests prove that login can do DML but cannot change the schema,
and that the migration hook secures tables added later.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal, describe_runtime_privileges
from tests.db_owner import owner_session_factory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "migrations"))
import db_security  # noqa: E402

OwnerSession = owner_session_factory()


async def test_suite_runs_as_least_privilege_login():
    async with AsyncSessionLocal() as session:
        info = await describe_runtime_privileges(session)
        member = (await session.execute(text("SELECT pg_has_role(current_user, 'flatmate_app', 'MEMBER')"))).scalar()
    assert info["role_name"] == "flatmate_api_test"
    assert info["least_privilege"] is True
    assert member is True


async def test_owner_connection_is_reported_as_overprivileged():
    async with OwnerSession() as session:
        info = await describe_runtime_privileges(session)
    assert info["least_privilege"] is False


@pytest.mark.parametrize("statement", [
    "CREATE TABLE public.attacker_table (id int)",
    "DROP TABLE public.users",
    "ALTER TABLE public.users ADD COLUMN pwned text",
    "ALTER TABLE public.users DISABLE ROW LEVEL SECURITY",
    "TRUNCATE public.messages",
    "CREATE FUNCTION public.pwn() RETURNS int LANGUAGE sql AS 'SELECT 1'",
    "DROP POLICY flatmate_app_all ON public.users",
    "UPDATE public.alembic_version SET version_num = 'x'",
    "DELETE FROM public.alembic_version",
    "SET ROLE postgres",
    "SELECT rolpassword FROM pg_authid",
    "CREATE ROLE intruder LOGIN SUPERUSER",
])
async def test_runtime_role_cannot_change_schema_or_escalate(statement):
    async with AsyncSessionLocal() as session:
        with pytest.raises(Exception) as exc:
            await session.execute(text(statement))
        await session.rollback()
    message = str(exc.value).lower()
    assert any(s in message for s in ("permission denied", "must be owner", "must be a member", "insufficient privilege")), message


async def test_runtime_role_cannot_grant_access_to_others():
    """Non-owners get only a warning from GRANT; verify that nothing was actually granted."""
    async with AsyncSessionLocal() as session:
        await session.execute(text("GRANT SELECT ON public.users TO PUBLIC"))
        granted = (await session.execute(text(
            "SELECT has_table_privilege('public', 'public.users', 'SELECT')"))).scalar()
        await session.rollback()
    assert granted is False


async def test_runtime_role_can_read_and_write_under_rls():
    async with AsyncSessionLocal() as session:
        await session.execute(text(
            "INSERT INTO outbox_events (id, event_type, payload, status, retry_count, created_at, next_attempt_at) "
            "VALUES (gen_random_uuid(), 'probe', '{}'::jsonb, 'published', 0, now(), now())"
        ))
        visible = (await session.execute(text("SELECT count(*) FROM outbox_events WHERE event_type = 'probe'"))).scalar()
        assert visible >= 1  # RLS policy admits the app role
        version = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        assert version >= "007"
        await session.rollback()


async def test_every_table_has_app_policy_and_api_roles_have_none():
    async with OwnerSession() as session:
        missing = (await session.execute(text("""
            SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
              AND NOT EXISTS (SELECT 1 FROM pg_depend d
                              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
              AND NOT EXISTS (SELECT 1 FROM pg_policies p
                              WHERE p.schemaname = 'public' AND p.tablename = c.relname
                                AND p.policyname = 'flatmate_app_all')
        """))).scalars().all()
        assert missing == [], f"Tables the API cannot reach under RLS: {missing}"

        roles = (await session.execute(text(
            "SELECT DISTINCT unnest(roles) FROM pg_policies WHERE schemaname = 'public'"
        ))).scalars().all()
        assert set(roles) == {"flatmate_app"}  # no policy ever admits anon/authenticated/public


async def test_migration_hook_secures_tables_added_later():
    async with OwnerSession() as session:
        try:
            await session.execute(text("CREATE TABLE public.future_feature (id int primary key)"))
            await session.execute(text(db_security.SECURE_TABLES_IF_ENABLED_SQL))
            rls = (await session.execute(text(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'future_feature'"))).scalar()
            policy = (await session.execute(text(
                "SELECT 1 FROM pg_policies WHERE tablename = 'future_feature' AND policyname = 'flatmate_app_all'"
            ))).scalar()
            grant = (await session.execute(text(
                "SELECT has_table_privilege('flatmate_app', 'public.future_feature', 'INSERT')"))).scalar()
            assert rls is True and policy == 1 and grant is True
        finally:
            await session.rollback()


async def test_migration_hook_is_a_noop_below_revision_007():
    """After a downgrade past 007, the env.py hook must not re-grant what was revoked."""
    async with OwnerSession() as session:
        try:
            await session.execute(text("UPDATE alembic_version SET version_num = '006_outbox_dispatch'"))
            await session.execute(text("CREATE TABLE public.after_downgrade (id int primary key)"))
            await session.execute(text(db_security.SECURE_TABLES_IF_ENABLED_SQL))
            policy = (await session.execute(text(
                "SELECT 1 FROM pg_policies WHERE tablename = 'after_downgrade'"))).scalar()
            assert policy is None
        finally:
            await session.rollback()
