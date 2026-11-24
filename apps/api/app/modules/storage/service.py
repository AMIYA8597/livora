"""
Secure File Storage Application Service
Enforces validation (magic bytes, MIME type, size limits),
resource authorization (property ownership, avatar identity, private verification),
and safe key generation.
"""
import asyncio
import uuid
import re
from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    InternalServerException,
)
from app.core.logging import logger
from app.infrastructure.images import ImageRejected, sanitize_image
from app.infrastructure.virus_scan import scan_bytes
from app.infrastructure.storage import get_storage, StorageProvider
from app.infrastructure.storage_buckets import BucketSpec, get_bucket
from app.modules.users.models import User
from app.modules.properties.models import Property
from app.modules.storage.schemas import UploadResponse

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024       # 10 MB for property images
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024        # 5 MB for profile avatars
MAX_DOC_SIZE_BYTES = 15 * 1024 * 1024         # 15 MB for verification documents

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_DOC_TYPES = {"image/jpeg", "image/png", "application/pdf", "image/webp"}
ALLOWED_BUCKETS = {"properties", "avatars", "verification", "chat_attachments"}
# Roles that may upload listing photos before the listing exists (create-listing flow).
LISTING_ROLES = {"owner", "pg_operator", "broker", "tenant", "admin", "super_admin"}
ADMIN_ROLES = {"admin", "super_admin", "moderator"}

# Magic byte signatures
MAGIC_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "application/pdf": [b"%PDF"],
    "image/webp": [b"RIFF"],
}

GENERIC_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

# PDF features that run code or carry other files. Names may be written with #xx escapes
# (/J#61vaScript), which _pdf_names undoes before matching.
PDF_ACTIVE_NAMES = (b"/javascript", b"/js", b"/launch", b"/embeddedfile", b"/embeddedfiles",
                    b"/richmedia", b"/xfa", b"/submitform", b"/importdata")
_PDF_NAME = re.compile(rb"/[^\s/<>\[\]()%{}]+")
_PDF_HEX = re.compile(rb"#([0-9A-Fa-f]{2})")


def sniff_content_type(content: bytes) -> Optional[str]:
    """The upload's real type from its leading bytes, for the types the platform accepts."""
    for mime in ("image/jpeg", "image/png"):
        if content.startswith(MAGIC_SIGNATURES[mime][0]):
            return mime
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _pdf_names(content: bytes) -> set:
    names = set()
    for match in _PDF_NAME.finditer(content):
        raw = _PDF_HEX.sub(lambda m: bytes([int(m.group(1), 16)]), match.group(0))
        names.add(raw.lower())
    return names


def pdf_active_content(content: bytes) -> Optional[str]:
    """Name of the first scripting/embedding feature found in a PDF, or None."""
    names = _pdf_names(content)
    for name in PDF_ACTIVE_NAMES:
        if name in names:
            return name.decode()[1:]
    return None


async def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload without holding more than `max_bytes` (+1 chunk) in memory."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(256 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise BadRequestException(
                f"File size exceeds maximum permitted limit of {max_bytes // (1024 * 1024)}MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


class MalwareScanner(ABC):
    @abstractmethod
    def scan(self, data: bytes) -> bool:
        """Return True if safe, False if malicious."""
        pass

class DefaultMalwareScanner(MalwareScanner):
    """Quick structural checks on every upload; ClamAV (when configured) runs after these."""

    EXECUTABLE_HEADERS = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"#!")

    def scan(self, data: bytes) -> bool:
        return not data.startswith(self.EXECUTABLE_HEADERS)

class StorageService:
    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        storage_provider: Optional[StorageProvider] = None,
        scanner: Optional[MalwareScanner] = None,
    ):
        self.db = db
        self.storage = storage_provider or get_storage()
        self.scanner = scanner or DefaultMalwareScanner()

    def validate_file(
        self,
        content: bytes,
        content_type: str,
        filename: Optional[str],
        bucket: str,
    ) -> str:
        """Validate file size, empty content, MIME type, magic bytes, and extension."""
        if not content or len(content) == 0:
            raise BadRequestException("Empty files cannot be uploaded")

        spec = self._spec(bucket)
        max_size = spec.max_bytes
        allowed_types = spec.mime_types

        if len(content) > max_size:
            limit_mb = max_size // (1024 * 1024)
            raise BadRequestException(f"File size exceeds maximum permitted limit of {limit_mb}MB")

        if content_type not in allowed_types:
            raise BadRequestException(
                f"Invalid file format '{content_type}'. Allowed: {', '.join(sorted(allowed_types))}"
            )

        # Magic byte signature check
        expected_sig = MAGIC_SIGNATURES.get(content_type)
        if expected_sig:
            matched = any(content.startswith(sig) for sig in expected_sig)
            if content_type == "image/webp" and matched:
                # Additional WebP check: must contain WEBP at bytes 8-12
                matched = len(content) >= 12 and content[8:12] == b"WEBP"
            if not matched:
                raise BadRequestException(
                    f"File content does not match declared MIME type {content_type} (spoofed signature detected)"
                )

        if content_type == "application/pdf":
            feature = pdf_active_content(content)
            if feature:
                raise BadRequestException(
                    f"PDFs with active content ({feature}) aren't accepted. Print it to a new PDF and try again."
                )

        # Malware scanning
        if not self.scanner.scan(content):
            raise BadRequestException("Malware or disallowed executable binary detected in upload payload")

        # Sanitize extension
        raw_ext = (filename.split(".")[-1].lower() if filename and "." in filename else "").strip()
        safe_ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "application/pdf": "pdf",
        }
        return safe_ext_map.get(content_type, "bin" if not raw_ext else re.sub(r"[^a-z0-9]", "", raw_ext))

    @staticmethod
    def resolve_content_type(content: bytes, declared: Optional[str]) -> str:
        """
        Browsers and apps often send a generic type, so the type comes from the bytes when the
        client didn't name one. A specific declared type is kept, and validate_file rejects it
        if the bytes disagree.
        """
        declared = (declared or "").split(";")[0].strip().lower()
        if declared in GENERIC_TYPES:
            return sniff_content_type(content) or "application/octet-stream"
        if declared == "image/jpg":
            return "image/jpeg"
        return declared

    async def virus_scan(self, content: bytes) -> None:
        result = await scan_bytes(content)
        if result.verdict == "infected":
            logger.warning("Upload rejected by virus scan: %s", result.signature or "unknown signature")
            raise BadRequestException("This file was flagged by the virus scanner and can't be uploaded")
        if result.verdict in ("unavailable", "disabled") and settings.VIRUS_SCAN_REQUIRED:
            raise AppException(
                status_code=503, title="Service Unavailable", error_code="SCAN_UNAVAILABLE",
                detail="Uploads are paused while the virus scanner is unavailable. Try again shortly.",
            )

    @staticmethod
    def max_bytes_for(bucket: str) -> int:
        return StorageService._spec(bucket).max_bytes

    @staticmethod
    def _spec(bucket: str) -> BucketSpec:
        spec = get_bucket(bucket)
        if spec is None:
            raise BadRequestException(f"Invalid bucket. Allowed buckets: {', '.join(sorted(ALLOWED_BUCKETS))}")
        return spec

    @staticmethod
    def _roles(user: User) -> set:
        roles = {user.role}
        for r in getattr(user, "roles", None) or []:
            roles.add(getattr(r, "role", r))
        return roles

    async def authorize_upload(
        self,
        current_user: User,
        bucket: str,
        resource_id: Optional[str] = None,
        domain_authorized: bool = False,
    ) -> None:
        """Verify that current_user has permission to upload to the requested bucket and target resource."""
        spec = self._spec(bucket)
        if not spec.generic_upload and not domain_authorized:
            raise BadRequestException(
                "Uploads to this bucket go through their own endpoint (e.g. conversation attachments)"
            )

        is_admin = bool(self._roles(current_user) & ADMIN_ROLES)

        if bucket == "properties" and not resource_id and not (self._roles(current_user) & LISTING_ROLES):
            # Without this, any account could use the public bucket as free image hosting.
            raise ForbiddenException("Only listing owners can upload property photos")

        if bucket == "properties" and resource_id and self.db:
            try:
                prop_uuid = uuid.UUID(resource_id)
            except ValueError:
                raise BadRequestException("Invalid property UUID format")

            prop_query = select(Property).where(Property.id == prop_uuid)
            prop = (await self.db.execute(prop_query)).scalar_one_or_none()
            if not prop:
                raise NotFoundException("Target property not found")

            if prop.owner_id != current_user.id and not is_admin:
                raise ForbiddenException("You do not have permission to upload images for this property")

    async def upload_file(
        self,
        current_user: User,
        file_bytes: bytes,
        content_type: str,
        filename: Optional[str],
        bucket: str,
        purpose: Optional[str] = None,
        resource_id: Optional[str] = None,
        domain_authorized: bool = False,
    ) -> UploadResponse:
        """Validate, authorize, and persist uploaded file."""
        # 1. Authorize
        await self.authorize_upload(current_user, bucket, resource_id, domain_authorized)
        spec = self._spec(bucket)

        # 2. Validate content & get safe extension, then scan it
        content_type = self.resolve_content_type(file_bytes, content_type)
        safe_ext = self.validate_file(file_bytes, content_type, filename, bucket)
        await self.virus_scan(file_bytes)

        # 3. Re-encode images: strips EXIF/GPS, applies orientation, drops embedded payloads
        if content_type.startswith("image/"):
            try:
                file_bytes = await asyncio.to_thread(sanitize_image, file_bytes, content_type)
            except ImageRejected as exc:
                raise BadRequestException(str(exc))

        # 3b. Server-side randomized key generation (prevents overwriting & directory traversal)
        file_id = uuid.uuid4()
        if bucket == "properties" and resource_id:
            dest_path = f"prop_{resource_id}/{file_id}.{safe_ext}"
        else:
            dest_path = f"{current_user.id}/{file_id}.{safe_ext}"

        # 4. Storage provider upload
        try:
            stored_url = self.storage.upload_file(
                bucket=spec.physical,
                destination_path=dest_path,
                data=file_bytes,
                content_type=content_type,
            )
        except Exception as e:
            raise InternalServerException(f"Storage provider error: {str(e)}")

        is_private = not spec.public
        safe_url = stored_url if not is_private else self.storage.get_signed_url(bucket=spec.physical, path=dest_path, expires_in=3600)

        return UploadResponse(
            url=safe_url,
            file_url=safe_url,
            bucket=bucket,
            path=dest_path,
            content_type=content_type,
            size_bytes=len(file_bytes),
            object_id=str(file_id),
            purpose=purpose or bucket,
            resource_id=resource_id,
            is_private=is_private,
        )

    def get_signed_url(
        self,
        current_user: User,
        bucket: str,
        path: str,
        expires_in: int = 3600,
        domain_authorized: bool = False,
    ) -> str:
        """
        Generate a time-limited signed URL. The generic endpoint serves only buckets whose
        access rule it can enforce itself (verification: owner or admin). Chat attachments are
        signed only by the conversation endpoint, after it checks active membership.
        """
        # Path traversal guard
        if ".." in path or path.startswith("/") or "\\" in path or "\x00" in path:
            raise BadRequestException("Invalid path: path traversal detected")

        spec = self._spec(bucket)
        if spec.public:
            raise BadRequestException("Files in this bucket are public; use their stored URL")
        if not spec.generic_signed_url and not domain_authorized:
            raise ForbiddenException("Access to these files is granted through their own endpoint")

        # Verification bucket is private; only owner or admin can retrieve
        if bucket == "verification":
            is_admin = bool(self._roles(current_user) & ADMIN_ROLES)
            user_prefix = str(current_user.id)
            clean_parts = [p for p in path.replace("\\", "/").split("/") if p]
            if not is_admin and (not clean_parts or clean_parts[0] != user_prefix):
                raise ForbiddenException("Access denied: You can only access your own verification documents")

        return self.storage.get_signed_url(bucket=spec.physical, path=path, expires_in=expires_in)
