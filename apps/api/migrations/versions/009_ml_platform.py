"""AI/ML platform: content embeddings, listing full-text search, model registry, ranker features
and automatic moderation reports.

Revision ID: 009_ml_platform
Revises: 008_phone_verification

- `content_embeddings`: one vector per listing / profile, tagged with the model that produced it
  (vectors from different models are never compared). Stored as `real[]` everywhere; when the
  pgvector extension is available (Supabase), a `vector(512)` copy is kept in sync by a trigger
  and indexed with HNSW for approximate nearest-neighbour retrieval.
- `properties.search_tsv`: weighted full-text vector (title > locality > description) with a
  GIN index, for the lexical half of hybrid search.
- `ml_models`: versioned model registry (parameters + offline evaluation metrics). At most one
  active version per model name.
- `match_interactions.features`: the ranking features as they were when the user acted, so the
  ranker trains on what the user actually saw.
- `moderation_reports`: reports raised automatically have no reporter (`source = 'auto'`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op

revision: str = "009_ml_platform"
down_revision: Union[str, None] = "008_phone_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 512


def _pgvector_available(bind) -> bool:
    if context.is_offline_mode():
        return True
    return bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS content_embeddings (
            id UUID PRIMARY KEY,
            entity_type VARCHAR(32) NOT NULL,
            entity_id UUID NOT NULL,
            model VARCHAR(80) NOT NULL,
            embedding REAL[] NOT NULL,
            content_hash VARCHAR(64) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_content_embeddings_entity UNIQUE (entity_type, entity_id),
            CONSTRAINT ck_content_embeddings_type CHECK (entity_type IN ('property', 'profile'))
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_content_embeddings_type_model ON content_embeddings (entity_type, model)"
    ))

    op.execute(sa.text("""
        ALTER TABLE properties ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(address_display, '') || ' ' || coalesce(city, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
        ) STORED
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_properties_search_tsv ON properties USING gin (search_tsv)"))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ml_models (
            id UUID PRIMARY KEY,
            name VARCHAR(64) NOT NULL,
            version INTEGER NOT NULL,
            params JSONB NOT NULL,
            metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
            training_rows INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_ml_models_name_version UNIQUE (name, version)
        )
    """))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ml_models_one_active ON ml_models (name) WHERE is_active"
    ))

    op.execute(sa.text("ALTER TABLE match_interactions ADD COLUMN IF NOT EXISTS features JSONB"))

    op.execute(sa.text("ALTER TABLE moderation_reports ALTER COLUMN reporter_id DROP NOT NULL"))
    op.execute(sa.text(
        "ALTER TABLE moderation_reports ADD COLUMN IF NOT EXISTS source VARCHAR(16) NOT NULL DEFAULT 'user'"
    ))
    op.execute(sa.text("ALTER TABLE moderation_reports ADD COLUMN IF NOT EXISTS details JSONB"))
    # One automatic report per target: the moderation worker is at-least-once.
    op.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_moderation_reports_auto_target "
        "ON moderation_reports (target_type, target_id) WHERE source = 'auto'"
    ))

    if not _pgvector_available(bind):
        return

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector' AND typtype = 'd') THEN
                DROP DOMAIN vector;
            END IF;
        END $$;
    """)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"ALTER TABLE content_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector({EMBEDDING_DIM})")
    op.execute(f"""
        CREATE OR REPLACE FUNCTION content_embeddings_sync_vec() RETURNS trigger AS $$
        BEGIN
            IF cardinality(NEW.embedding) = {EMBEDDING_DIM} THEN
                NEW.embedding_vec := NEW.embedding::vector({EMBEDDING_DIM});
            ELSE
                NEW.embedding_vec := NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_content_embeddings_sync_vec ON content_embeddings")
    op.execute("""
        CREATE TRIGGER trg_content_embeddings_sync_vec
        BEFORE INSERT OR UPDATE OF embedding ON content_embeddings
        FOR EACH ROW EXECUTE FUNCTION content_embeddings_sync_vec()
    """)
    op.execute("UPDATE content_embeddings SET embedding = embedding")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_embeddings_vec_hnsw "
        "ON content_embeddings USING hnsw (embedding_vec vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_embeddings_vec_hnsw")
    op.execute("DROP TRIGGER IF EXISTS trg_content_embeddings_sync_vec ON content_embeddings")
    op.execute("DROP FUNCTION IF EXISTS content_embeddings_sync_vec()")
    op.execute("DROP INDEX IF EXISTS uq_moderation_reports_auto_target")
    op.execute("ALTER TABLE moderation_reports DROP COLUMN IF EXISTS details")
    op.execute("ALTER TABLE moderation_reports DROP COLUMN IF EXISTS source")
    op.execute("DELETE FROM moderation_reports WHERE reporter_id IS NULL")
    op.execute("ALTER TABLE moderation_reports ALTER COLUMN reporter_id SET NOT NULL")
    op.execute("ALTER TABLE match_interactions DROP COLUMN IF EXISTS features")
    op.execute("DROP TABLE IF EXISTS ml_models")
    op.execute("DROP INDEX IF EXISTS ix_properties_search_tsv")
    op.execute("ALTER TABLE properties DROP COLUMN IF EXISTS search_tsv")
    op.execute("DROP TABLE IF EXISTS content_embeddings")
