"""Work and college email verification by one-time code; ID-document checks switched off.

Revision ID: 011_email_verification
Revises: 010_billing

Data changes (not reversible by downgrade):
  * Pending requests from the old manual flow are cancelled: there is no review queue any more.
  * `users.is_verified` now means "has a verified work or college email". Badges granted by the
    old flow (placeholder documents, approve-only) are cleared.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_email_verification"
down_revision: Union[str, None] = "010_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for ddl in (
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS method VARCHAR(16) NOT NULL DEFAULT 'manual'",
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS email_domain VARCHAR(255)",
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS subject_hash VARCHAR(64)",
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS code_hash VARCHAR(64)",
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE verifications ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
        "CREATE INDEX IF NOT EXISTS ix_verifications_user_created ON verifications (user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_verifications_subject_created ON verifications (subject_hash, created_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_verifications_approved_subject ON verifications (subject_hash) "
        "WHERE status = 'approved' AND subject_hash IS NOT NULL",
        "UPDATE verifications SET status = 'cancelled' WHERE status = 'pending' AND method = 'manual'",
        """UPDATE users u SET is_verified = EXISTS (
               SELECT 1 FROM verifications v
               WHERE v.user_id = u.id AND v.status = 'approved' AND v.method <> 'manual'
                 AND v.verification_type IN ('work_email', 'student_email'))
           WHERE u.is_verified IS DISTINCT FROM EXISTS (
               SELECT 1 FROM verifications v
               WHERE v.user_id = u.id AND v.status = 'approved' AND v.method <> 'manual'
                 AND v.verification_type IN ('work_email', 'student_email'))""",
    ):
        op.execute(sa.text(ddl))


def downgrade() -> None:
    for ddl in (
        "DROP INDEX IF EXISTS uq_verifications_approved_subject",
        "DROP INDEX IF EXISTS ix_verifications_subject_created",
        "DROP INDEX IF EXISTS ix_verifications_user_created",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS expires_at",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS attempts",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS code_hash",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS subject_hash",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS email_domain",
        "ALTER TABLE verifications DROP COLUMN IF EXISTS method",
    ):
        op.execute(sa.text(ddl))
