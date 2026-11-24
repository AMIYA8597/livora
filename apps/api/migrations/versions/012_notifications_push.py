"""Notification centre and Web Push: categories and links, push subscriptions, preferences.

Revision ID: 012_notifications_push
Revises: 011_email_verification
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_notifications_push"
down_revision: Union[str, None] = "011_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for ddl in (
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS category VARCHAR(20) NOT NULL DEFAULT 'account'",
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS link VARCHAR(300)",
        "CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at)",
        # Older rows: derive what we can.
        """UPDATE notifications SET category = CASE
               WHEN notification_type = 'new_message' THEN 'messages'
               WHEN notification_type IN ('match_created', 'new_interest') THEN 'matches'
               WHEN notification_type IN ('application_received', 'application_status_change', 'appointment_requested',
                                          'appointment_status_change', 'viewing_reminder', 'property_enquiry',
                                          'listing_expiry') THEN 'rentals'
               ELSE 'account' END
           WHERE category = 'account'""",
        """CREATE TABLE IF NOT EXISTS push_subscriptions (
               id UUID PRIMARY KEY,
               user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
               endpoint TEXT NOT NULL UNIQUE,
               p256dh VARCHAR(200) NOT NULL,
               auth VARCHAR(100) NOT NULL,
               user_agent VARCHAR(300),
               failure_count INTEGER NOT NULL DEFAULT 0,
               last_success_at TIMESTAMPTZ,
               created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
               updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
        "CREATE INDEX IF NOT EXISTS ix_push_subscriptions_user_id ON push_subscriptions (user_id)",
        """CREATE TABLE IF NOT EXISTS notification_preferences (
               user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
               push_messages BOOLEAN NOT NULL DEFAULT true,
               push_matches BOOLEAN NOT NULL DEFAULT true,
               push_rentals BOOLEAN NOT NULL DEFAULT true,
               push_account BOOLEAN NOT NULL DEFAULT true,
               updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
           )""",
    ):
        op.execute(sa.text(ddl))
    # RLS + flatmate_app grants for the new tables are applied by the env.py hook.


def downgrade() -> None:
    for ddl in (
        "DROP TABLE IF EXISTS notification_preferences",
        "DROP TABLE IF EXISTS push_subscriptions",
        "DROP INDEX IF EXISTS ix_notifications_user_created",
        "ALTER TABLE notifications DROP COLUMN IF EXISTS link",
        "ALTER TABLE notifications DROP COLUMN IF EXISTS category",
    ):
        op.execute(sa.text(ddl))
