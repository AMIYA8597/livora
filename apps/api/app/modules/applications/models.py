import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import String, Numeric, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    applicant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False, index=True)
    introduction: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_rent: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    move_in_target: Mapped[date] = mapped_column(Date, nullable=False)
    documents: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applicant = relationship("User", foreign_keys=[applicant_id])
    property = relationship("Property")
    room = relationship("Room")
