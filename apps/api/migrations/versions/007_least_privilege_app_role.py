"""Least-privilege runtime role: DML-only `flatmate_app` group role with RLS policies.

The API should connect as a login user that is a member of `flatmate_app` (see
`scripts/create_app_db_user.sql`), never as the schema owner.

Revision ID: 007_least_privilege_app_role
Revises: 006_outbox_dispatch
"""
import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "007_least_privilege_app_role"
down_revision: Union[str, None] = "006_outbox_dispatch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_spec = importlib.util.spec_from_file_location("db_security", Path(__file__).resolve().parent.parent / "db_security.py")
assert _spec and _spec.loader
db_security = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(db_security)


def upgrade() -> None:
    op.execute(db_security.CREATE_APP_ROLE_SQL)
    op.execute(db_security.SECURE_TABLES_SQL)


def downgrade() -> None:
    op.execute(db_security.REMOVE_APP_ROLE_SQL)
