"""
Database privilege model, shared by migration 007 and `env.py`.

  * Migrations run as the schema owner (MIGRATION_DATABASE_URL).
  * The API runs as a login user that is a member of the NOLOGIN group role `flatmate_app`
    (DATABASE_URL). That role has DML on application tables only: no DDL, no TRUNCATE, no
    TRIGGER/REFERENCES, and read-only access to `alembic_version`. A SQL injection or a
    compromised API process therefore cannot drop, alter or create objects.
  * Every application table has RLS enabled (migration 005). A non-owner role sees no rows
    under RLS unless a policy admits it, so each table gets a `flatmate_app_all` policy for
    `flatmate_app` only. Supabase's `anon`/`authenticated` roles still have no grants and no
    policies, so they remain locked out.

`SECURE_TABLES_SQL` is idempotent. `env.py` runs it after every migration run, so a table
added by any future migration is secured automatically.
"""

APP_ROLE = "flatmate_app"
APP_POLICY = "flatmate_app_all"

CREATE_APP_ROLE_SQL = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;
"""

def _secure_tables_sql(require_revision_007: bool) -> str:
    guard = (
        "    IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num >= '007') THEN\n"
        "        RETURN;\n"
        "    END IF;\n"
    ) if require_revision_007 else ""
    return f"""
DO $$
DECLARE
    r record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        RETURN;
    END IF;
{guard}
    EXECUTE 'GRANT USAGE ON SCHEMA public TO {APP_ROLE}';

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
        IF r.relname = 'alembic_version' THEN
            EXECUTE format('REVOKE ALL ON public.%I FROM {APP_ROLE}', r.relname);
            EXECUTE format('GRANT SELECT ON public.%I TO {APP_ROLE}', r.relname);
        ELSE
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO {APP_ROLE}', r.relname);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'public' AND tablename = r.relname AND policyname = '{APP_POLICY}'
        ) THEN
            EXECUTE format(
                'CREATE POLICY {APP_POLICY} ON public.%I FOR ALL TO {APP_ROLE} USING (true) WITH CHECK (true)',
                r.relname
            );
        END IF;
    END LOOP;

    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}';

    -- Objects created later by the migrating role get the same grants.
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}';
END $$;
"""


# Used by migration 007 itself (alembic_version is updated only after it runs).
SECURE_TABLES_SQL = _secure_tables_sql(require_revision_007=False)
# Used by env.py after every run: a no-op below 007, so downgrades are not undone.
SECURE_TABLES_IF_ENABLED_SQL = _secure_tables_sql(require_revision_007=True)

REMOVE_APP_ROLE_SQL = f"""
DO $$
DECLARE
    r record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        RETURN;
    END IF;
    FOR r IN SELECT tablename FROM pg_policies WHERE schemaname = 'public' AND policyname = '{APP_POLICY}' LOOP
        EXECUTE format('DROP POLICY {APP_POLICY} ON public.%I', r.tablename);
    END LOOP;
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {APP_ROLE}';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {APP_ROLE}';
    EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}';
    EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE}';
    EXECUTE 'REVOKE ALL ON SCHEMA public FROM {APP_ROLE}';
    -- Roles are cluster-wide: keep the role if another database still grants it privileges.
    BEGIN
        EXECUTE 'DROP ROLE {APP_ROLE}';
    EXCEPTION WHEN dependent_objects_still_exist THEN
        RAISE NOTICE 'Role {APP_ROLE} kept: still referenced by another database';
    END;
END $$;
"""
