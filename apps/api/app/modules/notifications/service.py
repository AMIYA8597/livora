"""
In-app notifications, their live delivery, and push (Web Push to browsers, FCM/APNs to the apps).

`create_notification` stores the notification and, in the same commit, queues a `push.send`
outbox event when push is configured, the user has a browser subscribed or an app registered, and their preferences
allow the category. After the commit it broadcasts `notification.created` on the user's socket
and kicks the outbox. Message pushes are skipped while the recipient is connected: they see
the message live, and the chat has its own unread state.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.messaging.models import OutboxEvent
from app.modules.notifications.models import DevicePushToken, Notification, NotificationPreference, PushSubscription
from app.modules.notifications import native_push
from app.modules.notifications.push import PUSH_EVENT, push_enabled, validate_subscription, web_push_enabled

logger = logging.getLogger("flatmate.notifications")

CATEGORIES = ("messages", "matches", "rentals", "account")
TYPE_CATEGORY: Dict[str, str] = {
    "new_message": "messages",
    "match_created": "matches",
    "new_interest": "matches",
    "application_received": "rentals",
    "application_status_change": "rentals",
    "appointment_requested": "rentals",
    "appointment_status_change": "rentals",
    "viewing_reminder": "rentals",
    "property_enquiry": "rentals",
    "listing_expiry": "rentals",
    "billing": "account",
    "verification_result": "account",
    "role_request_result": "account",
}
SUPPORTED_NOTIFICATION_TYPES = set(TYPE_CATEGORY)
PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def category_for(notification_type: str) -> str:
    return TYPE_CATEGORY.get(notification_type, "account")


def safe_link(link: Optional[str]) -> Optional[str]:
    """Only same-site relative paths: a link can never send someone to another site."""
    if not link or not link.startswith("/") or link.startswith("//") or "\\" in link:
        return None
    return link[:300]


async def _is_online(user_id: UUID) -> bool:
    try:
        from app.modules.messaging.websocket import manager

        return await manager.is_online(str(user_id))
    except Exception:  # noqa: BLE001 - presence is best effort
        return False


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ reading

    async def list_for_user(
        self, user_id: UUID, unread_only: bool = False, before: Optional[datetime] = None, limit: int = PAGE_SIZE,
    ) -> List[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        if before is not None:
            query = query.where(Notification.created_at < before)
        query = query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(max(1, min(limit, MAX_PAGE_SIZE)))
        return list((await self.db.execute(query)).scalars().all())

    async def get_unread_count(self, user_id: UUID) -> int:
        res = await self.db.execute(
            select(func.count(Notification.id)).where(Notification.user_id == user_id, Notification.is_read.is_(False))
        )
        return int(res.scalar() or 0)

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        notif = (await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )).scalar_one_or_none()
        if not notif:
            raise NotFoundException("Notification not found")
        notif.is_read = True
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def mark_all_read(self, user_id: UUID) -> int:
        res = await self.db.execute(
            update(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False)).values(is_read=True)
        )
        await self.db.commit()
        return int(getattr(res, "rowcount", 0) or 0)  # CursorResult for UPDATE

    # ------------------------------------------------------------------ creating

    async def create_notification(
        self,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: str,
        reference_id: Optional[UUID] = None,
        idempotency_window_minutes: int = 5,
        link: Optional[str] = None,
        push: bool = True,
    ) -> Notification:
        # The same event for the same thing within the window is one notification while it's
        # still unread; once the user has read it, the next event notifies again.
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=idempotency_window_minutes)
        existing = (await self.db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.notification_type == notification_type,
                Notification.reference_id.is_(None) if reference_id is None else Notification.reference_id == reference_id,
                Notification.is_read.is_(False),
                Notification.created_at >= recent_cutoff,
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            return existing

        category = category_for(notification_type)
        notif = Notification(
            user_id=user_id,
            title=title[:200],
            body=body,
            notification_type=notification_type,
            category=category,
            link=safe_link(link),
            reference_id=reference_id,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(notif)
        await self.db.flush()

        queued_push = False
        if push and await self._should_push(user_id, category):
            self.db.add(OutboxEvent(event_type=PUSH_EVENT, status="pending", payload={
                "user_id": str(user_id), "id": str(notif.id), "title": notif.title, "body": notif.body,
                "link": notif.link, "category": category,
            }))
            queued_push = True
        await self.db.commit()
        await self.db.refresh(notif)

        try:
            from app.modules.messaging.websocket import manager

            await manager.broadcast_to_users(
                event_type="notification.created",
                data={
                    "id": str(notif.id),
                    "user_id": str(notif.user_id),
                    "title": notif.title,
                    "body": notif.body,
                    "notification_type": notif.notification_type,
                    "category": notif.category,
                    "link": notif.link,
                    "reference_id": str(notif.reference_id) if notif.reference_id else None,
                    "is_read": False,
                    "created_at": notif.created_at.isoformat(),
                },
                user_ids=[user_id],
            )
        except Exception:  # noqa: BLE001 - live delivery is best effort; the row is stored
            logger.debug("notification broadcast failed", exc_info=True)

        if queued_push:
            from app.workers.outbox import schedule_dispatch

            schedule_dispatch()
        return notif

    async def _should_push(self, user_id: UUID, category: str) -> bool:
        if not push_enabled():
            return False
        if not await self._has_push_target(user_id):
            return False
        prefs = await self.db.get(NotificationPreference, user_id)
        if prefs is not None and not getattr(prefs, f"push_{category}", True):
            return False
        if category == "messages" and await _is_online(user_id):
            return False
        return True

    async def _has_push_target(self, user_id: UUID) -> bool:
        """A browser subscribed (with Web Push on) or an app registered (with its platform on)."""
        if web_push_enabled() and (await self.db.execute(
            select(PushSubscription.id).where(PushSubscription.user_id == user_id).limit(1)
        )).scalar_one_or_none():
            return True
        platforms = native_push.enabled_platforms()
        return bool(platforms) and (await self.db.execute(
            select(DevicePushToken.id).where(
                DevicePushToken.user_id == user_id, DevicePushToken.platform.in_(platforms)
            ).limit(1)
        )).scalar_one_or_none() is not None

    # ------------------------------------------------------------------ preferences

    async def get_preferences(self, user_id: UUID) -> Dict[str, bool]:
        prefs = await self.db.get(NotificationPreference, user_id)
        return {c: (getattr(prefs, f"push_{c}") if prefs else True) for c in CATEGORIES}

    async def update_preferences(self, user_id: UUID, changes: Dict[str, Optional[bool]]) -> Dict[str, bool]:
        prefs = await self.db.get(NotificationPreference, user_id)
        if prefs is None:
            prefs = NotificationPreference(user_id=user_id)
            self.db.add(prefs)
        for c in CATEGORIES:
            if changes.get(c) is not None:
                setattr(prefs, f"push_{c}", bool(changes[c]))
        prefs.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return await self.get_preferences(user_id)

    # ------------------------------------------------------------------ push subscriptions

    async def subscribe(self, user_id: UUID, endpoint: str, p256dh: str, auth: str, user_agent: Optional[str]) -> int:
        validate_subscription(endpoint, p256dh, auth)
        now = datetime.now(timezone.utc)
        sub = (await self.db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint).with_for_update()
        )).scalar_one_or_none()
        if sub is None:
            self.db.add(PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth,
                                         user_agent=(user_agent or "")[:300] or None, updated_at=now))
        else:
            # A browser belongs to whoever subscribed it last (shared computers, account switch).
            sub.user_id, sub.p256dh, sub.auth = user_id, p256dh, auth
            sub.user_agent = (user_agent or "")[:300] or None
            sub.failure_count, sub.updated_at = 0, now
        await self.db.commit()
        return await self._subscription_count(user_id)

    async def unsubscribe(self, user_id: UUID, endpoint: str) -> int:
        sub = (await self.db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.user_id == user_id)
        )).scalar_one_or_none()
        if sub is not None:
            await self.db.delete(sub)
            await self.db.commit()
        return await self._subscription_count(user_id)

    async def _subscription_count(self, user_id: UUID) -> int:
        res = await self.db.execute(select(func.count(PushSubscription.id)).where(PushSubscription.user_id == user_id))
        return int(res.scalar() or 0)

    # ------------------------------------------------------------------ app devices

    async def register_device(self, user_id: UUID, platform: str, token: str, app_version: Optional[str]) -> int:
        """Save an installed app's push token (idempotent; also refreshes it). Accepted even
        while that platform's push is off, so devices are ready when it's switched on."""
        token = native_push.normalize_token(platform, token)
        now = datetime.now(timezone.utc)
        device = (await self.db.execute(
            select(DevicePushToken).where(DevicePushToken.token == token).with_for_update()
        )).scalar_one_or_none()
        if device is None:
            self.db.add(DevicePushToken(user_id=user_id, platform=platform, token=token,
                                        app_version=app_version, updated_at=now))
        else:
            # A device belongs to whoever registered it last (account switch on a shared phone).
            device.user_id, device.platform, device.app_version = user_id, platform, app_version
            device.failure_count, device.updated_at = 0, now
        await self.db.commit()
        return await self._device_count(user_id)

    async def unregister_device(self, user_id: UUID, token: str) -> int:
        """Forget a token (sign-out on that device). Only the owner's own token is removed."""
        cleaned = (token or "").strip()
        await self.db.execute(delete(DevicePushToken).where(
            DevicePushToken.user_id == user_id,
            DevicePushToken.token.in_({cleaned, cleaned.lower()}),
        ))
        await self.db.commit()
        return await self._device_count(user_id)

    async def _device_count(self, user_id: UUID) -> int:
        res = await self.db.execute(select(func.count(DevicePushToken.id)).where(DevicePushToken.user_id == user_id))
        return int(res.scalar() or 0)
