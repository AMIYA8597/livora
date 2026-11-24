import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str
    notification_type: str
    category: str = "account"
    link: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PushPreferences(BaseModel):
    messages: bool = True
    matches: bool = True
    rentals: bool = True
    account: bool = True


class PushPreferencesUpdate(BaseModel):
    messages: Optional[bool] = None
    matches: Optional[bool] = None
    rentals: Optional[bool] = None
    account: Optional[bool] = None


class PushKeys(BaseModel):
    p256dh: str = Field(..., min_length=20, max_length=200)
    auth: str = Field(..., min_length=10, max_length=100)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=1000)
    keys: PushKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=1000)


class PushConfigResponse(BaseModel):
    # Web Push (browsers): whether it's on, and the VAPID key to subscribe with.
    enabled: bool
    public_key: Optional[str] = None
    # App platforms whose native push is on ("android", "ios").
    native_platforms: List[str] = []


APP_VERSION_PATTERN = r"^\d{1,4}(\.\d{1,4}){0,3}$"


class DeviceRegisterRequest(BaseModel):
    platform: Literal["android", "ios"]
    token: str = Field(..., min_length=32, max_length=4096)
    app_version: Optional[str] = Field(None, max_length=32, pattern=APP_VERSION_PATTERN)


class DeviceUnregisterRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=4096)


class DeviceRegistrationResponse(BaseModel):
    registered: bool
    # How many app devices this account now has registered.
    devices: int
