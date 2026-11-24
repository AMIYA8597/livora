"""Facts about the API itself that clients need before anything else (no sign-in, always
reachable, even by an app version the API no longer serves)."""
from typing import Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.core.client_version import NATIVE_PLATFORMS, platform_config

router = APIRouter(prefix="/meta", tags=["Meta"])

API_VERSION = "v1"


class PlatformVersions(BaseModel):
    # Below this the API answers 426 and the app must update. None = no minimum.
    min_version: Optional[str] = None
    # The newest release, for an optional "update available" hint.
    latest_version: Optional[str] = None
    # Store page to send people to.
    update_url: Optional[str] = None


class AppConfigResponse(BaseModel):
    api_version: str
    android: PlatformVersions
    ios: PlatformVersions


@router.get("/app-config", response_model=AppConfigResponse)
async def app_config(response: Response):
    """API version and, per app platform, the supported and latest versions. Apps call this on
    start and after any 426 response."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return AppConfigResponse(api_version=API_VERSION,
                             **{p: PlatformVersions(**platform_config(p)) for p in NATIVE_PLATFORMS})
