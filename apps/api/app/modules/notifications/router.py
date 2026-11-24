from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter
from app.modules.notifications.native_push import enabled_platforms
from app.modules.notifications.push import web_push_enabled
from app.modules.notifications.schemas import (
    DeviceRegisterRequest,
    DeviceRegistrationResponse,
    DeviceUnregisterRequest,
    NotificationResponse,
    PushConfigResponse,
    PushPreferences,
    PushPreferencesUpdate,
    PushSubscriptionRequest,
    PushUnsubscribeRequest,
)
from app.modules.notifications.service import PAGE_SIZE, NotificationService
from app.modules.users.models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=List[NotificationResponse])
async def get_my_notifications(
    unread_only: bool = False,
    before: Optional[datetime] = Query(None, description="Return notifications older than this (paging)"),
    limit: int = Query(PAGE_SIZE, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationService(db).list_for_user(current_user.id, unread_only=unread_only, before=before, limit=limit)


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"unread_count": await NotificationService(db).get_unread_count(current_user.id)}


@router.post("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"updated": await NotificationService(db).mark_all_read(current_user.id)}


@router.get("/preferences", response_model=PushPreferences)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationService(db).get_preferences(current_user.id)


@router.put("/preferences", response_model=PushPreferences)
async def update_preferences(
    data: PushPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationService(db).update_preferences(current_user.id, data.model_dump())


@router.get("/push/config", response_model=PushConfigResponse)
async def push_config():
    """Whether Web Push is available (and the VAPID public key browsers subscribe with), and
    which app platforms have native push."""
    enabled = web_push_enabled()
    return PushConfigResponse(enabled=enabled, public_key=settings.VAPID_PUBLIC_KEY if enabled else None,
                              native_platforms=enabled_platforms())


@router.post(
    "/push/subscriptions",
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=3600, key_prefix="push_subscribe"))],
)
async def subscribe_push(
    data: PushSubscriptionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save this browser's push subscription (idempotent; also refreshes it)."""
    count = await NotificationService(db).subscribe(
        current_user.id, data.endpoint, data.keys.p256dh, data.keys.auth, request.headers.get("user-agent"),
    )
    return {"subscribed": True, "devices": count}


@router.post("/push/unsubscribe")
async def unsubscribe_push(
    data: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await NotificationService(db).unsubscribe(current_user.id, data.endpoint)
    return {"subscribed": False, "devices": count}


@router.post(
    "/push/devices",
    response_model=DeviceRegistrationResponse,
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=3600, key_prefix="push_device"))],
)
async def register_device(
    data: DeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the Android or iOS app's push token for this account (idempotent; call it on every
    app start and whenever the platform issues a new token)."""
    count = await NotificationService(db).register_device(current_user.id, data.platform, data.token, data.app_version)
    return DeviceRegistrationResponse(registered=True, devices=count)


@router.post("/push/devices/unregister", response_model=DeviceRegistrationResponse)
async def unregister_device(
    data: DeviceUnregisterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forget this device's token (call before signing out in the app)."""
    count = await NotificationService(db).unregister_device(current_user.id, data.token)
    return DeviceRegistrationResponse(registered=False, devices=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await NotificationService(db).mark_read(notification_id, current_user.id)
