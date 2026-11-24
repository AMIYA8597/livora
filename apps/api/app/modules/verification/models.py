import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Verification(Base):
    """
    One verification attempt for a user.

    Work and college emails are verified by a one-time code (`method="email_code"`): the row is
    `pending` while the code is outstanding and becomes `approved` once confirmed. Only the email
    domain and a keyed hash of the full address are stored, never the address itself.

    ID-document checks are switched off until a KYC provider is chosen; rows from the old
    manual flow (`method="manual"`) are kept for history but no longer count.
    """

    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    verification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # pending | approved | expired | superseded | cancelled | rejected
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual", nullable=False)
    document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # legacy manual flow only
    email_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trust_score_bonus: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        Index("ix_verifications_user_created", "user_id", "created_at"),
        Index("ix_verifications_subject_created", "subject_hash", "created_at"),
        # An email address can be verified on only one account.
        Index("uq_verifications_approved_subject", "subject_hash", unique=True,
              postgresql_where=text("status = 'approved' AND subject_hash IS NOT NULL")),
    )
