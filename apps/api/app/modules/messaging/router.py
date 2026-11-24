import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, UploadFile, File, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.core.exceptions import AppException, ForbiddenException, NotFoundException
from app.modules.users.models import User
from app.modules.messaging.models import Attachment, ConversationParticipant
from app.modules.messaging.schemas import (
    ConversationResponse, SendMessageRequest, CreateConversationRequest,
    EditMessageRequest, MarkReadRequest,
    ConversationPreferenceRequest, ConversationPreferenceResponse,
    AddParticipantRequest, AttachmentResponse
)
from app.modules.messaging.service import MessagingService, message_dict
from app.modules.messaging.websocket import manager, shares_conversation
from app.modules.storage.service import StorageService, read_upload
from app.core.rate_limit import RateLimiter
from app.ml.smart_replies import suggest_for_conversation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messaging", tags=["Messaging"])

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    return await service.list_conversations(current_user.id, status_filter=status, search_query=q)

@router.post(
    "/conversations", status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=3600, key_prefix="conversation_create"))],
)
async def create_conversation(
    req: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conv = await service.create_conversation(current_user.id, req)
    return {"conversation_id": conv.id}

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    return await service.get_conversation(conversation_id, current_user.id)

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    messages = await service.get_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
        limit=limit,
        before_id=before_id
    )
    # Opening the conversation (the newest page) marks it read. Loading older pages must not.
    if messages and before_id is None:
        try:
            await service.mark_read(conversation_id, current_user.id, messages[-1].id)
        except Exception:
            pass

    return [message_dict(m, list(m.attachments), include_reply=True) for m in messages]


@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    msg = await service.send_message(current_user.id, req)
    return message_dict(msg, await service.attachments_for(msg.id))

@router.post(
    "/conversations/{conversation_id}/suggestions",
    dependencies=[Depends(RateLimiter(max_requests=20, window_seconds=60, key_prefix="smart_replies"))],
)
async def suggest_replies(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Up to three suggested messages (icebreaker, reply or follow-up). Generated on request,
    never stored, never sent automatically. `source` is "ai" or "templates"."""
    result = await suggest_for_conversation(db, conversation_id, current_user.id)
    return {"suggestions": result.suggestions, "source": result.source, "mode": result.mode}

@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: UUID,
    req: EditMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    msg = await service.edit_message(message_id, current_user.id, req)
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "content": msg.content,
        "is_edited": msg.is_edited,
        "edited_at": msg.edited_at,
    }

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    msg = await service.delete_message(message_id, current_user.id)
    return {"message_id": msg.id, "is_deleted": True}

@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    conversation_id: UUID,
    req: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    await service.mark_read(conversation_id, current_user.id, req.last_read_message_id)

@router.patch("/conversations/{conversation_id}/preferences", response_model=ConversationPreferenceResponse)
async def update_preferences(
    conversation_id: UUID,
    req: ConversationPreferenceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    pref = await service.update_preferences(conversation_id, current_user.id, req)
    return pref

@router.post("/conversations/{conversation_id}/participants")
async def add_participant(
    conversation_id: UUID,
    req: AddParticipantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    part = await service.add_participant(conversation_id, current_user.id, req)
    return {"participant_id": part.id, "user_id": part.user_id, "role": part.role}

@router.delete("/conversations/{conversation_id}/participants/{user_id}")
async def remove_participant(
    conversation_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    await service.remove_participant(conversation_id, current_user.id, user_id)
    return {"status": "removed", "user_id": user_id}

@router.post(
    "/conversations/{conversation_id}/attachments", response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=600, key_prefix="chat_attachment"))],
)
async def upload_attachment(
    conversation_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Authorize active membership in conversation
    part_q = select(ConversationParticipant).where(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == current_user.id,
        ConversationParticipant.is_active.is_(True),
    )
    if not (await db.execute(part_q)).scalar_one_or_none():
        raise ForbiddenException("You cannot upload attachments to a conversation you are not part of")

    # 2. Validate and upload file via StorageService
    content_type = file.content_type or "application/octet-stream"
    storage_service = StorageService(db=db)
    file_bytes = await read_upload(file, storage_service.max_bytes_for("chat_attachments"))

    upload_res = await storage_service.upload_file(
        current_user=current_user,
        file_bytes=file_bytes,
        content_type=content_type,
        filename=file.filename,
        bucket="chat_attachments",
        purpose="chat_attachment",
        resource_id=str(conversation_id),
        domain_authorized=True,  # membership checked above
    )

    # 3. Create Attachment entity
    attachment = Attachment(
        conversation_id=conversation_id,
        uploader_id=current_user.id,
        file_name=file.filename or "attachment",
        file_path=upload_res.path,
        mime_type=content_type,
        file_size_bytes=len(file_bytes),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return AttachmentResponse(
        id=attachment.id,
        conversation_id=attachment.conversation_id,
        message_id=attachment.message_id,
        uploader_id=attachment.uploader_id,
        file_name=attachment.file_name,
        file_path=attachment.file_path,
        mime_type=attachment.mime_type,
        file_size_bytes=attachment.file_size_bytes,
        signed_url=upload_res.url,
        created_at=attachment.created_at,
    )

@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Find attachment
    att_q = select(Attachment).where(Attachment.id == attachment_id)
    attachment = (await db.execute(att_q)).scalar_one_or_none()
    if not attachment:
        raise NotFoundException("Attachment not found")

    # 2. Authorize that caller is active participant of this conversation
    part_q = select(ConversationParticipant).where(
        ConversationParticipant.conversation_id == attachment.conversation_id,
        ConversationParticipant.user_id == current_user.id,
        ConversationParticipant.is_active.is_(True),
    )
    if not (await db.execute(part_q)).scalar_one_or_none():
        raise ForbiddenException("You are not authorized to access attachments from this conversation")

    # 3. Generate signed URL
    storage_service = StorageService(db=db)
    signed_url = storage_service.get_signed_url(
        current_user=current_user,
        bucket="chat_attachments",
        path=attachment.file_path,
        expires_in=3600,
        domain_authorized=True,  # active membership checked above
    )
    return {"signed_url": signed_url, "file_name": attachment.file_name, "mime_type": attachment.mime_type}

@router.get("/presence/{user_id}")
async def get_user_presence(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
):
    # Presence is visible only to people who share a conversation with the user.
    if not await shares_conversation(current_user.id, user_id):
        raise NotFoundException("User not found")
    return await manager.presence_of(str(user_id))


WS_AUTH_TIMEOUT_SECONDS = 10
WS_MAX_FRAME_CHARS = 16_000
# Application close codes (4000-4999). The client renews its token on 4001 and stops on 4003.
WS_CLOSE_TOKEN_EXPIRED = 4001
WS_CLOSE_UNAUTHORIZED = 4003


async def authenticate_socket_token(token: object) -> Optional[Tuple[UUID, Optional[datetime]]]:
    """Validate a socket token exactly like an HTTP request would.

    Only access tokens are accepted (never refresh or reset tokens), and the account must still
    exist and be active. Returns (user_id, expiry) or None.
    """
    if not isinstance(token, str) or not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type", "access") != "access":
            return None
        user_id = UUID(str(payload.get("sub")))
    except Exception:
        return None
    async with AsyncSessionLocal() as db:
        is_active = (await db.execute(select(User.is_active).where(User.id == user_id))).scalar_one_or_none()
    if not is_active:
        return None
    exp = payload.get("exp")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if isinstance(exp, (int, float)) else None
    return user_id, expires_at


async def _account_active(user_id: UUID) -> bool:
    async with AsyncSessionLocal() as db:
        return bool((await db.execute(select(User.is_active).where(User.id == user_id))).scalar_one_or_none())


async def _active_recipients(db: AsyncSession, conversation_id: UUID, user_id: UUID) -> Optional[List[UUID]]:
    """Other active participants, or None if `user_id` is not an active participant."""
    rows = (await db.execute(
        select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.is_active.is_(True),
        )
    )).scalars().all()
    if user_id not in rows:
        return None
    return [uid for uid in rows if uid != user_id]


def _envelope(event: str, data: dict, correlation_id: Optional[str] = None) -> str:
    return json.dumps({
        "version": "1.0",
        "event": event,
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Realtime channel.

    The client opens the socket and sends `{"event": "auth", "data": {"token": "<access token>"}}`
    as its first frame. The token is never put in the URL, where proxies and access logs would
    record it. The socket closes with 4001 when the token expires (the client renews and
    reconnects) and with 4003 when the token is invalid or the account is disabled.
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=WS_AUTH_TIMEOUT_SECONDS)
        frame = json.loads(first) if len(first) <= WS_MAX_FRAME_CHARS else {}
        if not isinstance(frame, dict):
            frame = {}
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        await _close_quietly(websocket, WS_CLOSE_UNAUTHORIZED, "Authentication required")
        return
    raw_data = frame.get("data")
    data: dict = raw_data if isinstance(raw_data, dict) else {}
    auth = await authenticate_socket_token(data.get("token")) if frame.get("event") == "auth" else None
    if auth is None:
        await _close_quietly(websocket, WS_CLOSE_UNAUTHORIZED, "Authentication failed")
        return
    user_id, expires_at = auth
    user_id_str = str(user_id)

    if not await manager.connect(user_id_str, websocket):
        return

    expiry_task = asyncio.create_task(_close_at_expiry(websocket, expires_at)) if expires_at else None
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw) > WS_MAX_FRAME_CHARS:
                await websocket.send_text(_envelope("error", {"code": "FRAME_TOO_LARGE", "message": "Message too large"}))
                continue
            try:
                frame = json.loads(raw)
                if not isinstance(frame, dict):
                    raise ValueError("frame must be an object")
            except ValueError:
                await websocket.send_text(_envelope("error", {"code": "INVALID_JSON", "message": "Malformed JSON payload"}))
                continue
            await _handle_frame(websocket, user_id, frame)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - one bad socket must not crash the worker
        logger.warning("WebSocket loop ended: %s", type(exc).__name__)
    finally:
        if expiry_task:
            expiry_task.cancel()
        manager.disconnect(user_id_str, websocket)


async def _close_quietly(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except Exception:
        pass


async def _close_at_expiry(websocket: WebSocket, expires_at: datetime) -> None:
    delay = (expires_at - datetime.now(timezone.utc)).total_seconds()
    try:
        await asyncio.sleep(max(delay, 0))
    except asyncio.CancelledError:
        return
    await _close_quietly(websocket, WS_CLOSE_TOKEN_EXPIRED, "Token expired")


async def _handle_frame(websocket: WebSocket, user_id: UUID, frame: dict) -> None:
    """Handle one client frame. Each frame gets its own short database session, so an idle
    socket never holds a pooled connection."""
    event_type = frame.get("event")
    correlation_id = frame.get("correlation_id")
    raw_data = frame.get("data")
    data: dict = raw_data if isinstance(raw_data, dict) else {}

    if event_type == "ping":
        if manager.account_check_due(websocket) and not await _account_active(user_id):
            await _close_quietly(websocket, WS_CLOSE_UNAUTHORIZED, "Account disabled")
            return
        await manager.heartbeat(str(user_id), websocket)
        await websocket.send_text(_envelope("pong", {}, correlation_id))
        return

    if event_type in ("typing.started", "typing.stopped"):
        try:
            conv_id = UUID(str(data.get("conversation_id")))
        except ValueError:
            return
        async with AsyncSessionLocal() as db:
            recipients = await _active_recipients(db, conv_id, user_id)
        if recipients is None:
            return  # not a member: ignore silently
        if event_type == "typing.started":
            manager.handle_typing_start(str(conv_id), str(user_id), recipients)
        else:
            manager.handle_typing_stop(str(conv_id), str(user_id), recipients)
        return

    if event_type == "message.send":
        try:
            req = SendMessageRequest.model_validate({
                "conversation_id": data.get("conversation_id"),
                "content": (data.get("content") or "").strip(),
                "message_type": data.get("message_type", "text"),
                "idempotency_key": data.get("idempotency_key"),
                "reply_to_message_id": data.get("reply_to_message_id"),
                "attachment_ids": data.get("attachment_ids") or [],
                "metadata": data.get("metadata") or {},
            })
            async with AsyncSessionLocal() as db:
                await MessagingService(db).send_message(user_id, req)
        except AppException as exc:
            await websocket.send_text(_envelope("error", {"code": "SEND_ERROR", "message": exc.detail}, correlation_id))
        except ValidationError:
            await websocket.send_text(_envelope("error", {"code": "SEND_ERROR", "message": "Invalid message"}, correlation_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("WebSocket send failed: %s", type(exc).__name__)
            await websocket.send_text(_envelope("error", {"code": "SEND_ERROR", "message": "Couldn't send the message"}, correlation_id))
        return

    if event_type == "message.read":
        try:
            conv_id = UUID(str(data.get("conversation_id")))
            last_id = UUID(str(data["last_read_message_id"])) if data.get("last_read_message_id") else None
            async with AsyncSessionLocal() as db:
                await MessagingService(db).mark_read(conv_id, user_id, last_id)
        except (ValueError, AppException):
            pass
        return
