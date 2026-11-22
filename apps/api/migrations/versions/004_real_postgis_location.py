"""Replace fake PostGIS shims with real PostGIS and index property locations

Revision ID: 004_real_postgis_location
Revises: 003_pgvector_matching
Create Date: 2026-11-22 20:00:00.000000

Earlier versions of migration 001 swallowed a missing-PostGIS error and installed:
  * DOMAIN geometry AS text
  * plpgsql st_asewkb(...) returning ONE hardcoded point, so every property read back at the
    same coordinates
  * plpgsql st_geomfromewkt(...)

This migration detaches every spatial column from the fake domain, drops the shims, installs
the real extension, converts properties.location, cities.center_location and
localities.center_location to geometry(Point, 4326), and adds a GiST index on the
geography cast so radius queries (ST_DWithin on geography, in metres) are index-assisted.
It is a no-op for databases created with real PostGIS from the start, apart from the index.

Written as plain SQL with no Python-side introspection, so `alembic upgrade --sql` output works
in the Supabase SQL editor.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004_real_postgis_location"
down_revision: Union[str, None] = "003_pgvector_matching"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Detach from the fake domain, drop fake plpgsql shims, drop the fake domain.
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            -- Every column typed with the fake domain (properties.location,
            -- cities.center_location, localities.center_location) is detached to text first.
            FOR r IN
                SELECT c.relname AS tbl, a.attname AS col
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_type t ON t.oid = a.atttypid
                WHERE t.typname = 'geometry' AND t.typtype = 'd' AND c.relkind = 'r' AND NOT a.attisdropped
            LOOP
                EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE text USING %I::text', r.tbl, r.col, r.col);
            END LOOP;

            FOR r IN
                SELECT p.oid::regprocedure AS sig
                FROM pg_proc p JOIN pg_language l ON l.oid = p.prolang
                WHERE l.lanname = 'plpgsql' AND p.proname IN ('st_asewkb', 'st_geomfromewkt')
            LOOP
                EXECUTE 'DROP FUNCTION ' || r.sig;
            END LOOP;

            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'geometry' AND typtype = 'd') THEN
                DROP DOMAIN geometry;
            END IF;
        END $$;
        """
    )

    # 2. Real PostGIS. Fails loudly if the server does not have it installed.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 3. Convert every spatial column to a typed, SRID-constrained point.
    op.execute(
        """
        DO $$
        DECLARE
            spec record;
            coltype text;
        BEGIN
            FOR spec IN
                SELECT * FROM (VALUES
                    ('properties', 'location'),
                    ('cities', 'center_location'),
                    ('localities', 'center_location')
                ) AS v(tbl, col)
            LOOP
                SELECT format_type(a.atttypid, a.atttypmod) INTO coltype
                FROM pg_attribute a
                WHERE a.attrelid = spec.tbl::regclass AND a.attname = spec.col AND NOT a.attisdropped;

                IF coltype = 'text' THEN
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE geometry(Point, 4326) '
                        'USING ST_SetSRID(ST_GeomFromEWKT(%I), 4326)', spec.tbl, spec.col, spec.col);
                ELSIF coltype = 'geometry' THEN
                    EXECUTE format(
                        'ALTER TABLE %I ALTER COLUMN %I TYPE geometry(Point, 4326) '
                        'USING ST_SetSRID(%I, 4326)', spec.tbl, spec.col, spec.col);
                END IF;
            END LOOP;
        END $$;
        """
    )

    # 4. Index for metre-based radius search.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_properties_location_geog "
        "ON properties USING gist ((location::geography))"
    )


def downgrade() -> None:
    # The fake shims are intentionally not restored.
    op.execute("DROP INDEX IF EXISTS ix_properties_location_geog")
