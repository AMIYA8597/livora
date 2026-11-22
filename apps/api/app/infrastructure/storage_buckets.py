"""
Single source of truth for storage buckets.

The API speaks in logical bucket names (`properties`, `avatars`, `verification`,
`chat_attachments`); each maps to a physical bucket (configurable per environment) with
the visibility and server-side limits the platform expects. `scripts/provision_storage.py`
applies this to Supabase, and startup refuses to run if a private bucket is public.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional

from app.core.config import settings

MB = 1024 * 1024
IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
DOC_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"})


@dataclass(frozen=True)
class BucketSpec:
    logical: str
    physical: str
    public: bool
    max_bytes: int
    mime_types: FrozenSet[str]
    # Reachable from the generic /storage endpoints; otherwise only through its domain
    # endpoint (e.g. chat attachments via a conversation-authorised route).
    generic_upload: bool
    generic_signed_url: bool


def bucket_registry() -> Dict[str, BucketSpec]:
    return {
        "properties": BucketSpec("properties", settings.STORAGE_BUCKET_PROPERTIES, True, 10 * MB, IMAGE_TYPES, True, False),
        "avatars": BucketSpec("avatars", settings.STORAGE_BUCKET_AVATARS, True, 5 * MB, IMAGE_TYPES, True, False),
        "verification": BucketSpec("verification", settings.STORAGE_BUCKET_VERIFICATION, False, 15 * MB, DOC_TYPES, True, True),
        "chat_attachments": BucketSpec("chat_attachments", settings.STORAGE_BUCKET_CHAT_ATTACHMENTS, False, 15 * MB, DOC_TYPES, False, False),
    }


def get_bucket(logical: str) -> Optional[BucketSpec]:
    return bucket_registry().get(logical)
