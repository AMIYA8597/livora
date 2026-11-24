"""Push tokens of the Android and iOS apps (FCM and APNs), next to the browsers' Web Push
subscriptions. A token belongs to whoever registered it last; tokens the push service reports
gone are deleted, and ones that keep failing are dropped. Erased with the account; the
account export lists the devices but never the tokens (a token can notify that device).

Revision ID: 019_device_push_tokens
Revises: 018_listing_ranking
"""
from typing import Union

from alembic import op

revision: str = "019_device_push_tokens"
down_revision: Union[str, None] = "018_listing_ranking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS device_push_tokens (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform VARCHAR(10) NOT NULL,
            token TEXT NOT NULL UNIQUE,
            app_version VARCHAR(32),
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_success_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Separate from CREATE TABLE: on a fresh database migration 001 already built the table from
    # the models, so the IF NOT EXISTS above skips it.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_device_push_tokens_platform') THEN
                ALTER TABLE device_push_tokens ADD CONSTRAINT ck_device_push_tokens_platform
                    CHECK (platform IN ('android', 'ios'));
            END IF;
        END $$
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_device_push_tokens_user_id ON device_push_tokens (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS device_push_tokens")
