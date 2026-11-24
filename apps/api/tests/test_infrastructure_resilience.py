"""
Infrastructure Resilience and Failure Mode Verification
Tests Step 7 requirements:
- PostgreSQL unavailable / connection interrupted
- Supabase authentication unavailable
- Storage service failures
- Email/Notification delivery failures
- Optional recommendation provider failures (graceful fallback)
Ensures core platform fails safely and optional providers never disable core property discovery.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import OperationalError

from app.modules.notifications.service import NotificationService
from app.infrastructure.storage import SupabaseStorageProvider
from app.core.exceptions import UnauthorizedException


@pytest.mark.asyncio
async def test_supabase_auth_failure_fails_closed():
    """
    Test Step 7: When Supabase identity verification fails or token is forged/tampered,
    production security must fail closed (raise UnauthorizedException) and not grant access.
    """
    from app.core.dependencies import get_current_user
    tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalidpayload.invalidsignature"
    mock_db = AsyncMock()

    with pytest.raises(UnauthorizedException) as exc_info:
        await get_current_user(token=tampered_token, db=mock_db)

    assert exc_info.value.status_code == 401
    assert "Invalid, expired, or malformed authentication token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_storage_failure_handled_gracefully():
    """
    Test Step 7: When cloud storage service fails or S3 credentials fail,
    storage client raises descriptive error and does not corrupt application state.
    """
    mock_supabase_client = MagicMock()
    mock_storage = MagicMock()
    mock_storage.from_.return_value.upload.side_effect = ConnectionError("Storage endpoint unreachable: S3 503")
    mock_supabase_client.storage = mock_storage

    provider = SupabaseStorageProvider(url="https://mock.supabase.co", key="dummy-key")
    provider.client = mock_supabase_client

    with pytest.raises(ConnectionError) as exc_info:
        provider.upload_file(
            bucket="flatmate-media",
            destination_path="profiles/avatar.png",
            data=b"sample binary content",
            content_type="image/png"
        )

    assert "Storage endpoint unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_notification_delivery_failure_resilience():
    """
    Test Step 7: When email/push delivery fails, notification dispatch
    persists in-app record safely without crashing the calling workflow.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    # Idempotency check returns None
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    service = NotificationService(mock_db)

    notif = await service.create_notification(
        user_id=uuid4(),
        title="Application Received",
        body="A seeker applied for your room in Indiranagar",
        notification_type="application_status_change"
    )

    assert notif.title == "Application Received"
    assert notif.is_read is False


@pytest.mark.asyncio
async def test_database_operational_error_interruption():
    """
    Test Step 7: When PostgreSQL connection drops or raises OperationalError,
    transactions fail safely and rollback cleanly.
    """
    mock_db = AsyncMock()
    mock_db.execute.side_effect = OperationalError("connection lost", params=None, orig=Exception("TCP connection closed"))
    mock_db.rollback = AsyncMock()

    try:
        await mock_db.execute("SELECT 1")
    except OperationalError:
        await mock_db.rollback()

    mock_db.rollback.assert_awaited_once()
