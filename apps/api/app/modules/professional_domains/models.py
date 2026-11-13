"""
Professional Taxonomy Domain Models
Administratively configurable domains, professions, designations, and work schedules.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class ProfessionalDomain(Base):
    __tablename__ = "professional_domains"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    professions: Mapped[List["Profession"]] = relationship("Profession", back_populates="domain", cascade="all, delete-orphan")

class Profession(Base):
    __tablename__ = "professions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("professional_domains.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    domain: Mapped["ProfessionalDomain"] = relationship("ProfessionalDomain", back_populates="professions")
    designations: Mapped[List["Designation"]] = relationship("Designation", back_populates="profession", cascade="all, delete-orphan")

class Designation(Base):
    __tablename__ = "designations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profession_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("professions.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profession: Mapped["Profession"] = relationship("Profession", back_populates="designations")
