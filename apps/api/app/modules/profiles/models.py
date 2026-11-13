import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    education_institute: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    education_degree: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget_min: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    budget_max: Mapped[int] = mapped_column(Integer, default=2500, nullable=False)
    move_in_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lease_duration_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    lifestyle_vector: Mapped[list] = mapped_column(Vector(64), nullable=False)
    lifestyle_traits: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    preferred_locations: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="profile")
