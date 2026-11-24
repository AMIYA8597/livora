"""Account deletion: pending requests (30-day grace) and the erased-account marker.

Revision ID: 014_account_deletion
Revises: 013_application_status_history
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_account_deletion"
down_revision: Union[str, None] = "013_application_status_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for ddl in (
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
        """CREATE TABLE IF NOT EXISTS account_deletion_requests (
               user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
               requested_at TIMESTAMPTZ NOT NULL,
               purge_after TIMESTAMPTZ NOT NULL,
               cancellable BOOLEAN NOT NULL DEFAULT true,
               paused_property_ids JSONB NOT NULL DEFAULT '[]'::jsonb
           )""",
        """CREATE INDEX IF NOT EXISTS ix_account_deletion_requests_purge_after
               ON account_deletion_requests (purge_after)""",
    ):
        op.execute(sa.text(ddl))
    # RLS + flatmate_app grants for the new table are applied by the env.py hook.


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS account_deletion_requests"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at"))
