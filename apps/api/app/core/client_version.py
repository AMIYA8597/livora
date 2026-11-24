"""
Which app versions the API still serves.

The Android and iOS apps send `X-Client-Platform` (android | ios) and `X-Client-Version`
(dotted numbers, e.g. 1.4.0) on every request. When `MIN_APP_VERSION_<PLATFORM>` is set and the
app is older (or doesn't say its version), API calls answer 426 Upgrade Required with
`min_version` and `update_url`, so the app can show "Please update" instead of misbehaving
against an API it doesn't understand. The web app and other callers send no platform and are
never affected. `GET /api/v1/meta/app-config` is always answered, so an old app can still
learn where to update.

How to use it: additive API changes need nothing. Before removing or changing anything an old
app relies on, ship the app version that copes, wait for most people to update, raise the
minimum, then make the change (see docs/ARCHITECTURE.md, "For the mobile apps").
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from app.core.config import settings

NATIVE_PLATFORMS = ("android", "ios")
# Paths an outdated app can still reach: the config it needs to show the update screen, and
# health checks.
EXEMPT_PREFIXES = ("/api/v1/meta/", "/health", "/ready")
_VERSION = re.compile(r"^\d{1,4}(\.\d{1,4}){0,3}$")


def parse_version(value: Optional[str]) -> Optional[Tuple[int, ...]]:
    """(1, 4, 0) for "1.4" or "1.4.0"; None when it isn't a dotted version."""
    value = (value or "").strip()
    if not _VERSION.match(value):
        return None
    parts = [int(p) for p in value.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def platform_config(platform: str) -> dict:
    upper = platform.upper()
    return {
        "min_version": getattr(settings, f"MIN_APP_VERSION_{upper}"),
        "latest_version": getattr(settings, f"LATEST_APP_VERSION_{upper}"),
        "update_url": getattr(settings, f"APP_STORE_URL_{upper}"),
    }


def upgrade_required(platform: Optional[str], version: Optional[str]) -> Optional[dict]:
    """The platform's config when this app must update before using the API, else None."""
    platform = (platform or "").strip().lower()
    if platform not in NATIVE_PLATFORMS:
        return None
    config = platform_config(platform)
    minimum = parse_version(config["min_version"])
    if minimum is None:
        return None
    current = parse_version(version)
    if current is not None and current >= minimum:
        return None
    return config


def is_exempt(path: str) -> bool:
    return not path.startswith("/api/") or path.startswith(EXEMPT_PREFIXES)
