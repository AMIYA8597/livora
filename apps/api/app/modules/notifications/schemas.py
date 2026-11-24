import uuid
from datetime import datetime
from typing import Optional

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
    enabled: bool
    public_key: Optional[str] = None
