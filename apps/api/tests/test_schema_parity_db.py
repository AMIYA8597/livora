"""
A database built from empty must match one migrated step by step.

Migration 001 creates every table from the current models, so a later migration's
`CREATE TABLE IF NOT EXISTS` (with its constraints and defaults) is skipped on a fresh install.
The models therefore declare what those migrations added. CI builds its database from empty
(as the hosted one is), so this catches a model that drops one of them again.
"""
import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal

pytestmark = pytest.mark.asyncio

CONSTRAINTS = {
    ("content_embeddings", "uq_content_embeddings_entity"),
    ("content_embeddings", "ck_content_embeddings_type"),
    ("ml_models", "uq_ml_models_name_version"),
}

# Columns whose migrations set a database default (raw SQL inserts and admin fixes rely on it).
DEFAULTS = {
    "account_deletion_requests": ["cancellable", "paused_property_ids"],
    "application_status_events": ["by_staff", "created_at"],
    "billing_events": ["provider", "received_at", "status"],
    "content_embeddings": ["updated_at"],
    "listing_interactions": ["created_at"],
    "ml_models": ["created_at", "is_active", "metrics", "training_rows"],
    "moderation_reports": ["source"],
    "payments": ["provider"],
    "phone_verifications": ["attempts"],
    "subscription_plans": ["audience", "interval", "period", "sort_order"],
    "subscriptions": ["cancel_at_period_end", "provider", "updated_at"],
}


async def test_constraints_added_by_later_migrations_exist():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(
            "SELECT conrelid::regclass::text, conname FROM pg_constraint "
            "WHERE connamespace = 'public'::regnamespace"
        ))).all()
    assert CONSTRAINTS <= {(t, n) for t, n in rows}


async def test_columns_keep_their_database_defaults():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_default IS NOT NULL"
        ))).all()
    have = {(t, c) for t, c in rows}
    missing = [(t, c) for t, cols in DEFAULTS.items() for c in cols if (t, c) not in have]
    assert missing == []
