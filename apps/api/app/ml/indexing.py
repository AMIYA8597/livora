"""
Keeps `content_embeddings` in step with listings and profiles.

Writers call `queue_embedding_refresh` inside their transaction; the outbox worker then calls
`refresh_embedding`, which is idempotent: it skips work when the text (and model) are unchanged,
so at-least-once delivery and repeated saves cost nothing. `backfill` re-embeds everything,
e.g. after switching EMBEDDING_PROVIDER.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ml.embeddings import Embedder, content_hash, get_embedder, profile_text, property_text
from app.ml.models import ContentEmbedding
from app.modules.messaging.models import OutboxEvent
from app.modules.profiles.models import Profile
from app.modules.properties.models import Property

logger = logging.getLogger("flatmate.ml.indexing")

EMBEDDING_REFRESH_EVENT = "embedding.refresh"
ENTITY_TYPES = ("property", "profile")


def queue_embedding_refresh(db: AsyncSession, entity_type: str, entity_id: UUID) -> None:
    """Add (not commit) an outbox event; it commits with the caller's change."""
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unknown entity type {entity_type}")
    db.add(OutboxEvent(
        event_type=EMBEDDING_REFRESH_EVENT,
        payload={"entity_type": entity_type, "entity_id": str(entity_id)},
        status="pending",
    ))


async def _source_text(db: AsyncSession, entity_type: str, entity_id: UUID) -> Optional[str]:
    if entity_type == "property":
        prop = (await db.execute(
            select(Property).options(selectinload(Property.amenities)).where(Property.id == entity_id)
        )).scalar_one_or_none()
        if prop is None:
            return None
        return property_text(prop, [a.amenity_key for a in prop.amenities or []])
    profile = (await db.execute(select(Profile).where(Profile.user_id == entity_id))).scalar_one_or_none()
    return profile_text(profile) if profile is not None else None


async def refresh_embedding(
    db: AsyncSession, entity_type: str, entity_id: UUID, embedder: Optional[Embedder] = None
) -> str:
    """Returns "updated", "unchanged", "removed" or "empty". Commits."""
    embedder = embedder or get_embedder()
    source = await _source_text(db, entity_type, entity_id)
    existing = (await db.execute(select(ContentEmbedding).where(
        ContentEmbedding.entity_type == entity_type, ContentEmbedding.entity_id == entity_id,
    ))).scalar_one_or_none()

    if not source:
        if existing is not None:
            await db.execute(delete(ContentEmbedding).where(ContentEmbedding.id == existing.id))
            await db.commit()
            return "removed"
        return "empty"

    digest = content_hash(embedder.model_id, source)
    if existing is not None and existing.content_hash == digest:
        return "unchanged"

    [vector] = await embedder.embed([source], kind="document")
    now = datetime.now(timezone.utc)
    if existing is None:
        db.add(ContentEmbedding(
            entity_type=entity_type, entity_id=entity_id, model=embedder.model_id,
            embedding=vector, content_hash=digest, updated_at=now,
        ))
    else:
        existing.model = embedder.model_id
        existing.embedding = vector
        existing.content_hash = digest
        existing.updated_at = now
    await db.commit()
    return "updated"


@dataclass
class BackfillResult:
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    empty: int = 0


async def backfill(db: AsyncSession, entity_type: str, embedder: Optional[Embedder] = None) -> BackfillResult:
    embedder = embedder or get_embedder()
    if entity_type == "property":
        ids = (await db.execute(select(Property.id).where(Property.is_active.is_(True)))).scalars().all()
    else:
        ids = (await db.execute(select(Profile.user_id))).scalars().all()
    result = BackfillResult()
    for entity_id in ids:
        outcome = await refresh_embedding(db, entity_type, entity_id, embedder)
        setattr(result, outcome, getattr(result, outcome) + 1)
    return result


_VECTOR_INDEX: Optional[bool] = None


async def has_vector_index(db: AsyncSession) -> bool:
    """True when migration 009 created the pgvector column (cached per process)."""
    global _VECTOR_INDEX
    if _VECTOR_INDEX is None:
        _VECTOR_INDEX = (await db.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'content_embeddings' AND column_name = 'embedding_vec'"
        ))).scalar_one_or_none() is not None
    return bool(_VECTOR_INDEX)
