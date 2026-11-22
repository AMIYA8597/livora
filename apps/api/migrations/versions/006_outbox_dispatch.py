"""Outbox dispatch: retry scheduling, error capture and a pending-work index.

Revision ID: 006_outbox_dispatch
Revises: 005_lockdown_data_api
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_outbox_dispatch"
down_revision: Union[str, None] = "005_lockdown_data_api"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE outbox_events "
        "ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "ADD COLUMN IF NOT EXISTS last_error TEXT"
    ))
    # Dispatcher query: pending rows whose next attempt is due, oldest first.
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_outbox_pending_due "
        "ON outbox_events (next_attempt_at) WHERE status = 'pending'"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_outbox_pending_due"))
    op.execute(sa.text(
        "ALTER TABLE outbox_events DROP COLUMN IF EXISTS last_error, DROP COLUMN IF EXISTS next_attempt_at"
    ))
