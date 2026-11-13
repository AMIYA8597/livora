"""
Notification Service
Manages in-app notifications, event triggers, and idempotent background delivery.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.notifications.models import Notification
from app.core.exceptions import NotFoundException

SUPPORTED_NOTIFICATION_TYPES = {
    "match_created",
    "new_interest",
    "new_message",
    "property_enquiry",
    "application_status_change",
    "viewing_reminder",
    "verification_result",
    "listing_expiry",
}

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user_id: UUID, unread_only: bool = False) -> List[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        query = query.order_by(Notification.created_at.desc()).limit(30)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: str,
        reference_id: Optional[UUID] = None,
        idempotency_window_minutes: int = 5,
    ) -> Notification:
        # Idempotency check: prevent sending duplicate notification within window
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=idempotency_window_minutes)
        dup_query = select(Notification).where(
            Notification.user_id == user_id,
            Notification.notification_type == notification_type,
            Notification.reference_id == reference_id,
            Notification.created_at >= recent_cutoff
        )
        existing = (await self.db.execute(dup_query)).scalar_one_or_none()
        if existing:
            return existing  # Idempotently return existing notification without duplicating

        notif = Notification(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            reference_id=reference_id,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        query = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id
        )
        notif = (await self.db.execute(query)).scalar_one_or_none()
        if not notif:
            raise NotFoundException("Notification not found")
        notif.is_read = True
        await self.db.commit()
        await self.db.refresh(notif)
        return notif
