"""
Unit and Integration Tests for Verification Review, Moderation Reporting,
User Blocking, and Administrative Privileges.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.moderation.schemas import ReportCreate
from app.modules.moderation.service import ModerationService
from app.modules.moderation.models import UserBlock
from app.modules.verification.service import VerificationService
from app.modules.verification.models import Verification
from app.modules.administration.service import AdminService
from app.modules.users.models import User
from app.core.exceptions import BadRequestException, ConflictException

@pytest.mark.asyncio
async def test_moderation_report_submission_and_self_check():
    """Users can submit moderation reports; self-reporting is rejected."""
    reporter_id = uuid4()
    target_user_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = ModerationService(mock_db)

    # 1. Reporting yourself is rejected
    self_report = ReportCreate(
        target_type="user",
        target_id=reporter_id,
        reason="spam",
        description="test",
    )
    with pytest.raises(BadRequestException) as exc_info:
        await service.submit_report(reporter_id, self_report)
    assert "cannot report yourself" in str(exc_info.value.detail).lower()

    # 2. Legitimate report submission succeeds
    legit_report = ReportCreate(
        target_type="user",
        target_id=target_user_id,
        reason="harassment",
        description="Unsolicited abusive messages",
    )
    report = await service.submit_report(reporter_id, legit_report)
    assert report.status == "open"
    assert report.target_id == target_user_id
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_user_blocking_and_duplicate_prevention():
    """Users can block others; self-blocking and duplicate blocking are blocked."""
    user_id = uuid4()
    target_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = ModerationService(mock_db)

    # 1. Self block rejected
    with pytest.raises(BadRequestException) as exc_info:
        await service.block_user(user_id, user_id)
    assert "cannot block yourself" in str(exc_info.value.detail).lower()

    # 2. Duplicate block rejected
    existing_block = UserBlock(id=uuid4(), user_id=user_id, blocked_user_id=target_id)
    mock_exist_res = MagicMock()
    mock_exist_res.scalar_one_or_none.return_value = existing_block
    mock_db.execute.return_value = mock_exist_res

    with pytest.raises(ConflictException) as exc_info:
        await service.block_user(user_id, target_id)
    assert "already blocked" in str(exc_info.value.detail).lower()

    # 3. New block creation succeeds
    mock_free_res = MagicMock()
    mock_free_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_free_res

    block = await service.block_user(user_id, target_id)
    assert block.user_id == user_id
    assert block.blocked_user_id == target_id
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_verification_approval_updates_user():
    """Admin approving verification marks user as verified."""
    user_id = uuid4()
    verif_id = uuid4()

    mock_db = AsyncMock()
    service = VerificationService(mock_db)

    verif = Verification(
        id=verif_id,
        user_id=user_id,
        verification_type="government_id",
        status="pending",
    )
    user = User(
        id=user_id,
        email="verified@example.com",
        full_name="Verified User",
        is_verified=False,
    )

    mock_verif_res = MagicMock()
    mock_verif_res.scalar_one_or_none.return_value = verif

    mock_user_res = MagicMock()
    mock_user_res.scalar_one.return_value = user

    mock_db.execute.side_effect = [mock_verif_res, mock_user_res]

    approved = await service.approve_verification(verif_id)
    assert approved.status == "approved"
    assert user.is_verified is True
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_admin_user_deactivation_and_role_grant():
    """Admin can deactivate accounts and grant roles."""
    target_user_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = AdminService(mock_db)

    target_user = User(
        id=target_user_id,
        email="badactor@example.com",
        full_name="Bad Actor",
        is_active=True,
    )
    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = target_user
    mock_db.execute.return_value = mock_user_res

    # 1. Deactivate
    deactivated = await service.update_user_status(target_user_id, is_active=False)
    assert deactivated.is_active is False
    assert mock_db.commit.called

    # 2. Grant role
    mock_role_empty = MagicMock()
    mock_role_empty.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_user_res, mock_role_empty]

    role_granted = await service.grant_user_role(target_user_id, role="moderator")
    assert role_granted.role == "moderator"
    assert role_granted.user_id == target_user_id
