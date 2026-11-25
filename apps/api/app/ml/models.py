"""Tables owned by the ML platform (migration 009)."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContentEmbedding(Base):
    """One embedding per listing or profile, tagged with the model that produced it."""

    __tablename__ = "content_embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_content_embeddings_entity"),
        CheckConstraint("entity_type IN ('property', 'profile')", name="ck_content_embeddings_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # property, profile
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding: Mapped[List[float]] = mapped_column(ARRAY(Float(precision=24)), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()"))


class MLModel(Base):
    """Versioned model registry: parameters plus the offline metrics that justified activation."""

    __tablename__ = "ml_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ml_models_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default=text("'{}'::jsonb"))
    training_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()"))


class ListingInteraction(Base):
    """What a signed-in person was shown (impression, with the ranking features at that moment)
    and did (view, save, unsave) with listings (migration 018). Kept 180 days."""

    __tablename__ = "listing_interactions"
    __table_args__ = (
        Index("ix_listing_interactions_user_time", "user_id", "created_at"),
        Index("ix_listing_interactions_property", "property_id"),
        Index("ix_listing_interactions_time", "created_at"),
        CheckConstraint("action IN ('impression', 'view', 'save', 'unsave')", name="ck_listing_interactions_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # impression, view, save, unsave
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    features: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, server_default=text("now()"))
