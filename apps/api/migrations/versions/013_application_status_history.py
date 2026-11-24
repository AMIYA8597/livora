"""Application status history, so staff overrides (and every other change) leave a record.

Revision ID: 013_application_status_history
Revises: 012_notifications_push
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_application_status_history"
down_revision: Union[str, None] = "012_notifications_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for ddl in (
        """CREATE TABLE IF NOT EXISTS application_status_events (
               id UUID PRIMARY KEY,
               application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
               actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
               from_status VARCHAR(32) NOT NULL,
               to_status VARCHAR(32) NOT NULL,
               note TEXT,
               by_staff BOOLEAN NOT NULL DEFAULT false,
               created_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        """CREATE INDEX IF NOT EXISTS ix_application_status_events_app_created
               ON application_status_events (application_id, created_at)""",
    ):
        op.execute(sa.text(ddl))
    # RLS + flatmate_app grants for the new table are applied by the env.py hook.


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS application_status_events"))
