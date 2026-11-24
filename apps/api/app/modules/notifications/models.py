import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # messages | matches | rentals | account: what push preferences are keyed on.
    category: Mapped[str] = mapped_column(String(20), default="account", server_default="account", nullable=False)
    # In-app path to open (always a relative path built by the server).
    link: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)


class PushSubscription(Base):
    """One browser's Web Push subscription. The endpoint is unique: a browser belongs to whoever
    subscribed it last."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationPreference(Base):
    """Which categories may send a push. In-app notifications are always kept."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    push_messages: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    push_matches: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    push_rentals: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    push_account: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
