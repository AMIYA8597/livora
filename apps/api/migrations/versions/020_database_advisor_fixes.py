"""Fixes from Supabase's database advisor.

- The two trigger functions that keep the pgvector columns in sync get a fixed search_path,
  so a caller's search_path can't make them resolve to another schema's objects.
- Functions we own in `public` stop being executable by PUBLIC. Every role inherits that grant,
  so `anon` and `authenticated` could call them through `/rest/v1/rpc`, including Supabase's
  SECURITY DEFINER `rls_auto_enable()` behind the `ensure_rls` event trigger. Triggers and
  event triggers fire without an EXECUTE check, so nothing that uses them breaks. Functions
  that belong to extensions (PostGIS, pgvector, pg_trgm) are left alone: the API needs them.
- Migration 002's `idx_attachments_*` indexes duplicate the models' `ix_attachments_*`. Drop
  them.
- Every foreign key gets a covering index. Without one, deleting or updating the parent row
  (e.g. purging an account) scans the whole child table. The models declare the same indexes,
  so a database built from empty matches one migrated step by step.

Revision ID: 020_database_advisor_fixes
Revises: 019_device_push_tokens
"""
from typing import Union

from alembic import op

revision: str = "020_database_advisor_fixes"
down_revision: Union[str, None] = "019_device_push_tokens"
branch_labels = None
depends_on = None

SYNC_FUNCTIONS = ("profiles_sync_lifestyle_embedding", "content_embeddings_sync_vec")

DUPLICATE_INDEXES = {
    "idx_attachments_conv": "attachments (conversation_id)",
    "idx_attachments_msg": "attachments (message_id)",
    "idx_attachments_uploader": "attachments (uploader_id)",
}

FOREIGN_KEY_INDEXES = (
    ("application_status_events", "actor_id"),
    ("applications", "group_id"),
    ("applications", "room_id"),
    ("appointments", "applicant_id"),
    ("appointments", "host_id"),
    ("appointments", "room_id"),
    ("beds", "current_occupant_id"),
    ("cities", "state_id"),
    ("conversation_read_cursors", "last_read_message_id"),
    ("existing_tenant_vacancies", "posted_by_tenant_id"),
    ("existing_tenant_vacancies", "room_id"),
    ("group_members", "user_id"),
    ("group_wishlist_items", "added_by"),
    ("group_wishlist_items", "property_id"),
    ("groups", "creator_id"),
    ("messages", "reply_to_message_id"),
    ("moderation_reports", "reporter_id"),
    ("payments", "subscription_id"),
    ("property_amenities", "property_id"),
    ("states", "capital_city_id"),
    ("subscriptions", "plan_id"),
    ("tenant_memberships", "bed_id"),
    ("tenant_memberships", "room_id"),
)

# Our own functions in `public`: not part of an extension, owned by a role we act as.
_OWN_FUNCTIONS = """
    SELECT p.oid::regprocedure AS sig
    FROM pg_proc p
    WHERE p.pronamespace = 'public'::regnamespace
      AND pg_has_role(current_user, p.proowner, 'MEMBER')
      AND NOT EXISTS (
          SELECT 1 FROM pg_depend d
          WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
      )
"""


def _sync_function_names() -> str:
    return ", ".join(f"'{name}'" for name in SYNC_FUNCTIONS)


def upgrade() -> None:
    # The functions exist only where pgvector is installed (migrations 003 and 009).
    op.execute(
        f"""
        DO $$
        DECLARE f record;
        BEGIN
            FOR f IN
                SELECT p.oid::regprocedure AS sig FROM pg_proc p
                WHERE p.pronamespace = 'public'::regnamespace
                  AND p.proname IN ({_sync_function_names()})
            LOOP
                EXECUTE format('ALTER FUNCTION %s SET search_path = pg_catalog, public', f.sig);
            END LOOP;
        END $$
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE
            f record;
            api_role text;
        BEGIN
            FOR f IN {_OWN_FUNCTIONS}
            LOOP
                EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f.sig);
                FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
                        EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM %I', f.sig, api_role);
                    END IF;
                END LOOP;
            END LOOP;
        END $$
        """
    )
    for name in DUPLICATE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    for table, column in FOREIGN_KEY_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})")


def downgrade() -> None:
    for table, column in FOREIGN_KEY_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_{column}")
    for name, target in DUPLICATE_INDEXES.items():
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")
    op.execute(
        f"""
        DO $$
        DECLARE f record;
        BEGIN
            FOR f IN {_OWN_FUNCTIONS}
            LOOP
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO PUBLIC', f.sig);
            END LOOP;
        END $$
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE f record;
        BEGIN
            FOR f IN
                SELECT p.oid::regprocedure AS sig FROM pg_proc p
                WHERE p.pronamespace = 'public'::regnamespace
                  AND p.proname IN ({_sync_function_names()})
            LOOP
                EXECUTE format('ALTER FUNCTION %s RESET search_path', f.sig);
            END LOOP;
        END $$
        """
    )
