"""pgvector-backed lifestyle embeddings and matching retrieval indexes

Revision ID: 003_pgvector_matching
Revises: 002_messaging_realtime
Create Date: 2026-11-22 12:00:00.000000

Adds a real `vector(64)` column (`profiles.lifestyle_embedding`) with an HNSW cosine index,
kept in sync with `profiles.lifestyle_vector` by a trigger. The application ORM keeps using
`lifestyle_vector`; only the recommendation retrieval query reads the embedding.

When the pgvector extension is not installed on the server (some local dev boxes), the
vector parts are skipped and the matching service falls back to non-ANN retrieval.
Supabase ships pgvector, so hosted environments always get the index.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "003_pgvector_matching"
down_revision: Union[str, None] = "002_messaging_realtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 64


def _pgvector_available(bind) -> bool:
    # Offline (--sql) scripts target Supabase, which always ships pgvector.
    if context.is_offline_mode():
        return True
    return bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    # Retrieval pre-filter indexes (useful with or without pgvector).
    op.execute("CREATE INDEX IF NOT EXISTS ix_profiles_budget_range ON profiles (budget_min, budget_max)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_blocks_user_id ON user_blocks (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_blocks_blocked_user_id ON user_blocks (blocked_user_id)")

    if not _pgvector_available(bind):
        return

    # Migration 001 creates a placeholder DOMAIN named `vector` when pgvector is missing.
    # It is unused by any column, but it would block CREATE EXTENSION, so remove it first.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector' AND typtype = 'd') THEN
                DROP DOMAIN vector;
            END IF;
        END $$;
        """
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(f"ALTER TABLE profiles ADD COLUMN IF NOT EXISTS lifestyle_embedding vector({EMBEDDING_DIM})")

    # All-zero vectors (profiles that never finished the lifestyle quiz) have undefined cosine
    # distance, so they are stored as NULL and sort last.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION profiles_sync_lifestyle_embedding() RETURNS trigger AS $$
        BEGIN
            IF NEW.lifestyle_vector IS NULL
               OR cardinality(NEW.lifestyle_vector) <> {EMBEDDING_DIM}
               OR NOT EXISTS (SELECT 1 FROM unnest(NEW.lifestyle_vector) v WHERE v <> 0) THEN
                NEW.lifestyle_embedding := NULL;
            ELSE
                NEW.lifestyle_embedding := NEW.lifestyle_vector::vector({EMBEDDING_DIM});
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_profiles_sync_lifestyle_embedding ON profiles")
    op.execute(
        """
        CREATE TRIGGER trg_profiles_sync_lifestyle_embedding
        BEFORE INSERT OR UPDATE OF lifestyle_vector ON profiles
        FOR EACH ROW EXECUTE FUNCTION profiles_sync_lifestyle_embedding()
        """
    )

    # Backfill existing rows through the trigger.
    op.execute("UPDATE profiles SET lifestyle_vector = lifestyle_vector")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_profiles_lifestyle_embedding_hnsw "
        "ON profiles USING hnsw (lifestyle_embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_profiles_lifestyle_embedding_hnsw")
    op.execute("DROP TRIGGER IF EXISTS trg_profiles_sync_lifestyle_embedding ON profiles")
    op.execute("DROP FUNCTION IF EXISTS profiles_sync_lifestyle_embedding()")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS lifestyle_embedding")
    op.execute("DROP INDEX IF EXISTS ix_user_blocks_blocked_user_id")
    op.execute("DROP INDEX IF EXISTS ix_user_blocks_user_id")
    op.execute("DROP INDEX IF EXISTS ix_profiles_budget_range")
