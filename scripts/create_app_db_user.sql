-- Create (or rotate the password of) the API's least-privilege database login.
--
-- Run as the schema owner AFTER `alembic upgrade head` (migration 007 creates the
-- `flatmate_app` group role this login joins):
--
--   psql "$MIGRATION_DATABASE_URL" -v app_user=flatmate_api -v app_password='<strong random secret>' \
--        -f scripts/create_app_db_user.sql
--
-- Then point the API's DATABASE_URL at this login. On Supabase's pooler, the username is
-- "<app_user>.<project-ref>", e.g.
--   postgresql+asyncpg://flatmate_api.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
-- Keep MIGRATION_DATABASE_URL (the owner) for CI/CD migrations only, never in the API runtime.

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE %I LOGIN IN ROLE flatmate_app', :'app_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT PASSWORD %L',
              :'app_user', :'app_password')
\gexec

SELECT format('GRANT flatmate_app TO %I', :'app_user')
\gexec

-- Bound the damage of runaway or abusive queries from the API.
SELECT format('ALTER ROLE %I SET statement_timeout = %L', :'app_user', '15s')
\gexec
SELECT format('ALTER ROLE %I SET idle_in_transaction_session_timeout = %L', :'app_user', '30s')
\gexec
