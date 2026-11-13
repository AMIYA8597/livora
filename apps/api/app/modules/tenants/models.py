"""
Tenancy Memberships, Household Roster, and Vacancy Listings Domain Models
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    bed_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("beds.id", ondelete="SET NULL"), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    lease_start: Mapped[date] = mapped_column(Date, nullable=False)
    lease_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False) # active, notice_period, vacated, terminated
    is_primary_tenant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    property = relationship("Property")
    room = relationship("Room")
    tenant = relationship("User", foreign_keys=[tenant_id])

class ExistingTenantVacancy(Base):
    """Created by current tenants searching for a flatmate to fill a vacant room in their existing lease."""
    __tablename__ = "existing_tenant_vacancies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    posted_by_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    vacant_from: Mapped[date] = mapped_column(Date, nullable=False)
    expected_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_required: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    preferred_gender: Mapped[str] = mapped_column(String(32), default="any", nullable=False) # any, female_only, male_only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    property = relationship("Property")
    room = relationship("Room")
    posted_by = relationship("User", foreign_keys=[posted_by_tenant_id])
