"""Lock down the Supabase Data API: RLS on every table, no anon/authenticated access

Revision ID: 005_lockdown_data_api
Revises: 004_real_postgis_location
Create Date: 2026-11-22 21:00:00.000000

Architecture: the FastAPI backend is the ONLY data path. It connects as the table owner, which
bypasses RLS. The web app never queries Supabase tables directly (it only uses Supabase Auth).

Supabase exposes every `public` table through PostgREST to the `anon` role (whose key ships in
the frontend) and to `authenticated`. Before this migration, no Alembic migration enabled RLS,
so a hosted deploy would have exposed every table, including password hashes, KYC documents and
messages. The hand-maintained database/policies/rls_policies.sql was never applied by
migrations, covered only 21 of 44 tables, and let anyone read active users' rows.

This migration:
  1. enables RLS on every table in `public` (skipping extension-owned tables such as PostGIS's
     spatial_ref_sys, which the project owner cannot alter on Supabase). With no policies, this
     is default-deny for every non-owner role.
  2. revokes all table, sequence and function privileges in `public` from anon/authenticated,
     and changes default privileges so tables created later are not exposed either.
Step 2 runs only where those roles exist (Supabase); plain PostgreSQL has no such roles.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005_lockdown_data_api"
down_revision: Union[str, None] = "004_real_postgis_location"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

API_ROLES = ("anon", "authenticated")

LOCKDOWN_SQL = """
DO $$
DECLARE
    r record;
    api_role text;
BEGIN
    -- 1. Default-deny RLS on every application table.
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND NOT EXISTS (
              SELECT 1 FROM pg_depend d
              WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e'
          )
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
    END LOOP;

    -- 2. Remove Data API access for Supabase's API roles, now and for future objects.
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
            EXECUTE format('REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', api_role);
            EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM %I', api_role);
        END IF;
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(LOCKDOWN_SQL)


def downgrade() -> None:
    # Re-exposing every table to the public API is never a safe automatic rollback.
    # Restore grants manually and deliberately if the architecture changes.
    pass
