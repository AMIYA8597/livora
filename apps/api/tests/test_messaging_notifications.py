"""
Unit and Integration Tests for Messaging Authorization, Persistence,
and Notification Delivery.
"""
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.messaging.schemas import SendMessageRequest
from app.modules.messaging.service import MessagingService
from app.modules.messaging.models import ConversationParticipant, Message
from app.modules.notifications.service import NotificationService
from app.modules.notifications.models import Notification
from app.core.exceptions import ForbiddenException

@pytest.mark.asyncio
async def test_messaging_participant_authorization_get_messages():
    """Only conversation participants can read conversation messages."""
    user_a = uuid4()
    stranger = uuid4()
    conv_id = uuid4()

    mock_db = AsyncMock()
    service = MessagingService(mock_db)

    # 1. Non-participant check returns None -> ForbiddenException
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with pytest.raises(ForbiddenException) as exc_info:
        await service.get_messages(conv_id, stranger)
    assert "not a participant" in str(exc_info.value.detail).lower()

    # 2. Participant check succeeds
    mock_part = ConversationParticipant(conversation_id=conv_id, user_id=user_a)
    mock_part_res = MagicMock()
    mock_part_res.scalar_one_or_none.return_value = mock_part

    msg = Message(id=uuid4(), conversation_id=conv_id, sender_id=user_a, content="Hey!")
    mock_msg_res = MagicMock()
    mock_msg_res.scalars.return_value.all.return_value = [msg]

    mock_db.execute.side_effect = [mock_part_res, mock_msg_res]
    messages = await service.get_messages(conv_id, user_a)
    assert len(messages) == 1
    assert messages[0].content == "Hey!"

@pytest.mark.asyncio
async def test_messaging_participant_authorization_send_message():
    """Only conversation participants can post messages to a conversation."""
    sender_id = uuid4()
    conv_id = uuid4()

    mock_db = AsyncMock()
    service = MessagingService(mock_db)

    req = SendMessageRequest(
        conversation_id=conv_id,
        content="Is the room still available?",
        message_type="text",
        metadata={"attachment_count": 0}
    )

    # Non-participant attempt raises ForbiddenException
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with pytest.raises(ForbiddenException) as exc_info:
        await service.send_message(sender_id, req)
    assert "not authorized to send messages" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
async def test_notification_creation_and_idempotency():
    """Notification service dispatches notifications idempotently without duplicating."""
    user_id = uuid4()
    ref_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = NotificationService(mock_db)

    # 1. Existing recent notification check returns existing notification (Idempotent)
    existing_notif = Notification(
        id=uuid4(),
        user_id=user_id,
        title="New Match!",
        body="You matched with Priya",
        notification_type="match_created",
        reference_id=ref_id,
        is_read=False,
    )
    mock_exist_res = MagicMock()
    mock_exist_res.scalar_one_or_none.return_value = existing_notif
    mock_db.execute.return_value = mock_exist_res

    res = await service.create_notification(
        user_id=user_id,
        title="New Match!",
        body="You matched with Priya",
        notification_type="match_created",
        reference_id=ref_id,
    )
    assert res.id == existing_notif.id
    # Ensure add was not called again
    assert not mock_db.add.called

    # 2. When no duplicate exists, creates and commits new notification
    mock_free_res = MagicMock()
    mock_free_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_free_res

    new_res = await service.create_notification(
        user_id=user_id,
        title="Viewing Confirmed",
        body="Host confirmed your viewing for Saturday.",
        notification_type="viewing_reminder",
        reference_id=uuid4(),
    )
    assert new_res.title == "Viewing Confirmed"
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_notification_mark_read():
    """User can mark their notifications as read."""
    user_id = uuid4()
    notif_id = uuid4()

    mock_db = AsyncMock()
    service = NotificationService(mock_db)

    notif = Notification(
        id=notif_id,
        user_id=user_id,
        title="Application Update",
        body="Your application was accepted",
        notification_type="application_status_change",
        is_read=False,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = notif
    mock_db.execute.return_value = mock_res

    updated = await service.mark_read(notif_id, user_id)
    assert updated.is_read is True
    assert mock_db.commit.called
