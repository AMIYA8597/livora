"""
User, Multi-Role RBAC, and Privacy Settings Models
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="seeker") # Primary active role
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    # Set when the account has been erased: the row stays as an anonymous tombstone so messages
    # others received and de-identified payment records keep a valid reference.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Multi-Role & Profile Relationships
    roles: Mapped[List["UserRole"]] = relationship("UserRole", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    privacy_settings: Mapped[Optional["UserPrivacySetting"]] = relationship("UserPrivacySetting", back_populates="user", uselist=False, cascade="all, delete-orphan")
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserRole(Base):
    __tablename__ = "user_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False) # e.g. seeker, tenant, owner, pg_operator, broker, admin
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_role"),)

    user: Mapped["User"] = relationship("User", back_populates="roles")

class UserPrivacySetting(Base):
    __tablename__ = "user_privacy_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    show_phone_publicly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_exact_location: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_direct_messages: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    profile_visibility: Mapped[str] = mapped_column(String(32), default="public", nullable=False) # public, matched_only, private
    # Rank listings using what this person viewed, saved and applied to (migration 018).
    personalized_ranking: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="privacy_settings")


class AccountDeletionRequest(Base):
    """A pending deletion. The account is hidden and signed out until `purge_after`, when the
    maintenance job erases it; signing in before then cancels (unless staff locked the account)."""
    __tablename__ = "account_deletion_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cancellable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Listings that were published when the request was made, so cancelling can restore them.
    paused_property_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
