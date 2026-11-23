"""Real phone verification: one-time code table and users.phone_verified_at.

Revision ID: 008_phone_verification
Revises: 007_least_privilege_app_role
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_phone_verification"
down_revision: Union[str, None] = "007_least_privilege_app_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMPTZ"))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS phone_verifications (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            phone_e164 VARCHAR(20) NOT NULL,
            code_hash VARCHAR(64) NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            expires_at TIMESTAMPTZ NOT NULL,
            consumed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_phone_verifications_user_created ON phone_verifications (user_id, created_at)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_phone_verifications_phone_created ON phone_verifications (phone_e164, created_at)"))
    # A number can be verified on only one account. Partial unique index = race-proof.
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_verified_phone ON users (phone_number) "
        "WHERE phone_verified_at IS NOT NULL"
    ))
    # RLS + flatmate_app grant/policy for the new table are applied by the env.py hook.


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_users_verified_phone"))
    op.execute(sa.text("DROP TABLE IF EXISTS phone_verifications"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS phone_verified_at"))
