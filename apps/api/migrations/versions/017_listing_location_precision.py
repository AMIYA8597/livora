"""How precise a listing's map position is.

city     - still at its city's centre; the geocoding job will try to place it
locality - placed from its public locality, city and PIN code (OpenStreetMap)
postcode - placed from its PIN code only
owner    - the owner's own pin (e.g. a phone's location)
NULL     - listings saved before this column (positions came from seeds or older clients)

Revision ID: 017_listing_location_precision
Revises: 016_india_locations
"""
from typing import Union

from alembic import op

revision: str = "017_listing_location_precision"
down_revision: Union[str, None] = "016_india_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS location_precision VARCHAR(16)")
    op.execute(
        "ALTER TABLE properties ADD CONSTRAINT ck_properties_location_precision "
        "CHECK (location_precision IN ('city', 'locality', 'postcode', 'owner'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE properties DROP CONSTRAINT IF EXISTS ck_properties_location_precision")
    op.execute("ALTER TABLE properties DROP COLUMN IF EXISTS location_precision")
