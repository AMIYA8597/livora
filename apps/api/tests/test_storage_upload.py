"""
Unit and Integration Tests for Authenticated Storage Upload & Retrieval API
Verifies validation (magic bytes, MIME types, size limits), authorization checks,
isolated path generation, private document protection, and error handling.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.storage.service import StorageService
from app.modules.storage.schemas import UploadResponse
from app.infrastructure.storage import LocalStorageProvider
from app.modules.users.models import User
from app.modules.properties.models import Property
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    InternalServerException,
)

from tests.image_samples import make_image

# Real sample payloads (images must decode: uploads are re-encoded)
VALID_JPEG = make_image("JPEG")
VALID_PNG = make_image("PNG")
VALID_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"\x00" * 100
VALID_WEBP = make_image("WEBP")
SPOOFED_JPEG = b"NOT_A_REAL_JPEG_FILE_JUST_TEXT"
MALICIOUS_EXE = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100

@pytest.fixture
def mock_storage():
    storage = MagicMock(spec=LocalStorageProvider)
    storage.upload_file.return_value = "/uploads/mock/file.jpg"
    storage.get_signed_url.return_value = "/uploads/mock/file.jpg?expires=3600"
    return storage

@pytest.fixture
def normal_user():
    return User(
        id=uuid.uuid4(),
        email="seeker@example.com",
        role="seeker",
        is_active=True,
    )

@pytest.fixture
def owner_user():
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        role="owner",
        is_active=True,
    )

@pytest.fixture
def admin_user():
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        role="admin",
        is_active=True,
    )

@pytest.mark.asyncio
async def test_valid_property_image_upload(mock_storage, owner_user):
    service = StorageService(storage_provider=mock_storage)
    res = await service.upload_file(
        current_user=owner_user,
        file_bytes=VALID_JPEG,
        content_type="image/jpeg",
        filename="living_room.jpg",
        bucket="properties",
        purpose="listing_gallery",
    )
    assert isinstance(res, UploadResponse)
    assert res.bucket == "properties"
    assert res.content_type == "image/jpeg"
    assert res.size_bytes > 0  # re-encoded size, metadata stripped
    assert res.is_private is False
    assert mock_storage.upload_file.called

@pytest.mark.asyncio
async def test_valid_profile_avatar_upload(mock_storage, normal_user):
    service = StorageService(storage_provider=mock_storage)
    res = await service.upload_file(
        current_user=normal_user,
        file_bytes=VALID_PNG,
        content_type="image/png",
        filename="profile.png",
        bucket="avatars",
        purpose="avatar",
    )
    assert res.bucket == "avatars"
    assert res.path.startswith(str(normal_user.id))
    assert res.is_private is False

@pytest.mark.asyncio
async def test_valid_private_document_upload(mock_storage, normal_user):
    service = StorageService(storage_provider=mock_storage)
    res = await service.upload_file(
        current_user=normal_user,
        file_bytes=VALID_PDF,
        content_type="application/pdf",
        filename="aadhar_card.pdf",
        bucket="verification",
        purpose="identity_document",
    )
    assert res.bucket == "verification"
    assert res.is_private is True
    # Private document must return signed url rather than raw public bucket URL
    assert "expires=" in res.url
    assert mock_storage.get_signed_url.called

@pytest.mark.asyncio
async def test_unauthorized_property_image_upload(mock_storage, normal_user, owner_user):
    """A user who does not own the property must not be allowed to upload images for it."""
    prop_id = uuid.uuid4()
    mock_db = AsyncMock()
    mock_property = Property(id=prop_id, owner_id=owner_user.id, title="Test Villa")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_property
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = StorageService(db=mock_db, storage_provider=mock_storage)
    with pytest.raises(ForbiddenException) as exc_info:
        await service.upload_file(
            current_user=normal_user,
            file_bytes=VALID_JPEG,
            content_type="image/jpeg",
            filename="front.jpg",
            bucket="properties",
            resource_id=str(prop_id),
        )
    assert "permission" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_unauthorized_document_retrieval(mock_storage, normal_user):
    """A user cannot generate a signed URL for another user's private documents."""
    other_user_id = uuid.uuid4()
    forbidden_path = f"{other_user_id}/secret_id.pdf"

    service = StorageService(storage_provider=mock_storage)
    with pytest.raises(ForbiddenException) as exc_info:
        service.get_signed_url(
            current_user=normal_user,
            bucket="verification",
            path=forbidden_path,
        )
    assert "access denied" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_admin_can_retrieve_verification_document(mock_storage, admin_user):
    """Moderator/Admin can access any user's verification documents for review."""
    target_user_id = uuid.uuid4()
    target_path = f"{target_user_id}/kyc.pdf"

    service = StorageService(storage_provider=mock_storage)
    signed_url = service.get_signed_url(
        current_user=admin_user,
        bucket="verification",
        path=target_path,
    )
    assert signed_url is not None

def test_spoofed_mime_type(mock_storage):
    """File declared as JPEG but containing plain text must fail signature validation."""
    service = StorageService(storage_provider=mock_storage)
    with pytest.raises(BadRequestException) as exc_info:
        service.validate_file(
            content=SPOOFED_JPEG,
            content_type="image/jpeg",
            filename="fake.jpg",
            bucket="properties",
        )
    assert "spoofed" in str(exc_info.value).lower()

def test_unsupported_file_type(mock_storage):
    service = StorageService(storage_provider=mock_storage)
    with pytest.raises(BadRequestException) as exc_info:
        service.validate_file(
            content=b"some binary payload",
            content_type="application/x-msdownload",
            filename="script.exe",
            bucket="properties",
        )
    assert "invalid file format" in str(exc_info.value).lower()

def test_oversized_upload(mock_storage):
    service = StorageService(storage_provider=mock_storage)
    huge_payload = b"\xff\xd8\xff" + b"\x00" * (12 * 1024 * 1024) # 12MB > 10MB limit
    with pytest.raises(BadRequestException) as exc_info:
        service.validate_file(
            content=huge_payload,
            content_type="image/jpeg",
            filename="large.jpg",
            bucket="properties",
        )
    assert "exceeds maximum permitted limit" in str(exc_info.value).lower()

def test_empty_file_upload(mock_storage):
    service = StorageService(storage_provider=mock_storage)
    with pytest.raises(BadRequestException) as exc_info:
        service.validate_file(
            content=b"",
            content_type="image/jpeg",
            filename="empty.jpg",
            bucket="properties",
        )
    assert "empty" in str(exc_info.value).lower()

def test_malware_detection(mock_storage):
    """Malware scanner flags Windows/Linux executable binaries embedded in upload."""
    service = StorageService(storage_provider=mock_storage)
    with pytest.raises(BadRequestException) as exc_info:
        service.validate_file(
            content=MALICIOUS_EXE,
            content_type="image/jpeg",
            filename="pic.jpg",
            bucket="properties",
        )
    assert "malware" in str(exc_info.value).lower() or "spoofed" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_invalid_target_resource_not_found(mock_storage, owner_user):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    service = StorageService(db=mock_db, storage_provider=mock_storage)
    with pytest.raises(NotFoundException) as exc_info:
        await service.upload_file(
            current_user=owner_user,
            file_bytes=VALID_JPEG,
            content_type="image/jpeg",
            filename="img.jpg",
            bucket="properties",
            resource_id=str(uuid.uuid4()),
        )
    assert "not found" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_storage_provider_failure(owner_user):
    failing_storage = MagicMock()
    failing_storage.upload_file.side_effect = RuntimeError("MinIO Connection Refused")

    service = StorageService(storage_provider=failing_storage)
    with pytest.raises(InternalServerException) as exc_info:
        await service.upload_file(
            current_user=owner_user,
            file_bytes=VALID_JPEG,
            content_type="image/jpeg",
            filename="img.jpg",
            bucket="properties",
        )
    assert "storage provider error" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_api_unauthenticated_upload(async_client):
    """POST /api/v1/storage/upload without auth token returns 401."""
    files = {"file": ("test.jpg", VALID_JPEG, "image/jpeg")}
    response = await async_client.post("/api/v1/storage/upload", files=files, data={"bucket": "properties"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_api_authenticated_upload_success(async_client):
    """POST /api/v1/storage/upload with valid token returns 201."""
    test_email = f"uploader_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post("/api/v1/auth/register", json={
        "email": test_email,
        "password": "Password123!",
        "full_name": "Uploader User",
        "role": "owner",
        "phone_number": "+919876543210",
    })
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("listing.png", VALID_PNG, "image/png")}
    response = await async_client.post(
        "/api/v1/storage/upload",
        files=files,
        data={"bucket": "properties"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["bucket"] == "properties"
    assert body["content_type"] == "image/png"
    assert "url" in body
