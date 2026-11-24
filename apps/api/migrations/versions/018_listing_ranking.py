"""Per-person listing ranking: what each signed-in person was shown and did, and their opt-out.

listing_interactions
    impression - shown in a ranked results page (with the ranking features at that moment,
                 which the learned ranker trains on, and the position it was shown at)
    view       - opened the listing
    save/unsave - the heart on a card
    Applications are read from `applications`; nothing is duplicated here. Rows are kept 180
    days (maintenance job), exported with the account and erased with it.

user_privacy_settings.personalized_ranking
    Off: nothing is recorded and results ignore past activity (stated budget and move-in date
    from the profile still count).

Revision ID: 018_listing_ranking
Revises: 017_listing_location_precision
"""
from typing import Union

from alembic import op

revision: str = "018_listing_ranking"
down_revision: Union[str, None] = "017_listing_location_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS listing_interactions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
            action VARCHAR(16) NOT NULL,
            position INTEGER,
            features JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Separate from CREATE TABLE: on a fresh database migration 001 already built the table from
    # the models, so the IF NOT EXISTS above skips it.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_listing_interactions_action') THEN
                ALTER TABLE listing_interactions ADD CONSTRAINT ck_listing_interactions_action
                    CHECK (action IN ('impression', 'view', 'save', 'unsave'));
            END IF;
        END $$
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_listing_interactions_user_time ON listing_interactions (user_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_listing_interactions_property ON listing_interactions (property_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_listing_interactions_time ON listing_interactions (created_at)")
    op.execute(
        "ALTER TABLE user_privacy_settings "
        "ADD COLUMN IF NOT EXISTS personalized_ranking BOOLEAN NOT NULL DEFAULT true"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE user_privacy_settings DROP COLUMN IF EXISTS personalized_ranking")
    op.execute("DROP TABLE IF EXISTS listing_interactions")
