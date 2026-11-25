"""Role requests: someone asks for a role that staff grant after a check (brokers). One open
request per person and role; staff approve (the role is granted) or decline with a note.
Erased with the account (ON DELETE CASCADE); listed in the account export.

Revision ID: 021_role_requests
Revises: 020_database_advisor_fixes
"""
from typing import Union

from alembic import op

revision: str = "021_role_requests"
down_revision: Union[str, None] = "020_database_advisor_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS role_requests (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(32) NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            note TEXT,
            decision_note TEXT,
            decided_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_at TIMESTAMPTZ
        )
        """
    )
    # Separate from CREATE TABLE: on a fresh database migration 001 already built the table from
    # the models, so the IF NOT EXISTS above skips it.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_role_requests_status') THEN
                ALTER TABLE role_requests ADD CONSTRAINT ck_role_requests_status
                    CHECK (status IN ('pending', 'approved', 'declined'));
            END IF;
        END $$
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_role_requests_user_id ON role_requests (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_role_requests_decided_by ON role_requests (decided_by)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_role_requests_status_created ON role_requests (status, created_at)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_requests_open ON role_requests (user_id, role) "
        "WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_requests")
