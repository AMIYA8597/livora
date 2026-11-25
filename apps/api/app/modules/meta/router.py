"""Facts about the API itself that clients need before anything else (no sign-in, always
reachable, even by an app version the API no longer serves)."""
from typing import Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.client_version import NATIVE_PLATFORMS, platform_config
from app.infrastructure.sms import phone_verification_available
from app.modules.billing.razorpay import billing_enabled

router = APIRouter(prefix="/meta", tags=["Meta"])

API_VERSION = "v1"


class PlatformVersions(BaseModel):
    # Below this the API answers 426 and the app must update. None = no minimum.
    min_version: Optional[str] = None
    # The newest release, for an optional "update available" hint.
    latest_version: Optional[str] = None
    # Store page to send people to.
    update_url: Optional[str] = None


class Features(BaseModel):
    # Optional features that depend on paid providers. Off means the app hides them rather than
    # showing something that would fail.
    phone_verification: bool  # SMS codes (SMS_PROVIDER=disabled turns it off)
    payments: bool  # paid plans (Razorpay keys set)


class AppConfigResponse(BaseModel):
    api_version: str
    android: PlatformVersions
    ios: PlatformVersions
    features: Features


@router.get("/app-config", response_model=AppConfigResponse)
async def app_config(response: Response):
    """API version, per app platform the supported and latest versions, and which optional
    features are on. Apps call this on start and after any 426 response."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return AppConfigResponse(
        api_version=API_VERSION,
        features=Features(phone_verification=phone_verification_available(), payments=billing_enabled()),
        **{p: PlatformVersions(**platform_config(p)) for p in NATIVE_PLATFORMS},
    )
