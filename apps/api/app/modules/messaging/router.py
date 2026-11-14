import json
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.users.models import User
from app.modules.messaging.models import Attachment, ConversationParticipant
from app.modules.messaging.schemas import (
    ConversationResponse, SendMessageRequest, CreateConversationRequest,
    EditMessageRequest, MarkReadRequest,
    ConversationPreferenceRequest, ConversationPreferenceResponse,
    AddParticipantRequest, AttachmentResponse
)
from app.modules.messaging.service import MessagingService
from app.modules.messaging.websocket import manager
from app.modules.storage.service import StorageService

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

@router.post("/conversations", status_code=status.HTTP_201_CREATED)
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
    if messages:
        try:
            await service.mark_read(conversation_id, current_user.id, messages[-1].id)
        except Exception:
            pass

    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "sender_id": m.sender_id,
            "content": m.content if not getattr(m, "is_deleted", False) else "This message was deleted.",
            "message_type": m.message_type,
            "idempotency_key": getattr(m, "idempotency_key", None),
            "reply_to_message_id": getattr(m, "reply_to_message_id", None),
            "reply_to": {
                "id": m.reply_to.id,
                "sender_id": m.reply_to.sender_id,
                "content": m.reply_to.content if not getattr(m.reply_to, "is_deleted", False) else "This message was deleted.",
            } if getattr(m, "reply_to", None) else None,
            "is_edited": getattr(m, "is_edited", False),
            "edited_at": getattr(m, "edited_at", None),
            "is_deleted": getattr(m, "is_deleted", False),
            "deleted_at": getattr(m, "deleted_at", None),
            "metadata": getattr(m, "metadata_", {}),
            "is_read": m.is_read,
            "sent_at": m.sent_at,
            "attachments": [
                {
                    "id": a.id,
                    "conversation_id": a.conversation_id,
                    "message_id": a.message_id,
                    "uploader_id": a.uploader_id,
                    "file_name": a.file_name,
                    "file_path": a.file_path,
                    "mime_type": a.mime_type,
                    "file_size_bytes": a.file_size_bytes,
                    "created_at": a.created_at,
                } for a in getattr(m, "attachments", [])
            ],
        }
        for m in messages
    ]

@router.post("/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    msg = await service.send_message(current_user.id, req)
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "message_type": msg.message_type,
        "idempotency_key": msg.idempotency_key,
        "reply_to_message_id": msg.reply_to_message_id,
        "is_edited": msg.is_edited,
        "is_deleted": msg.is_deleted,
        "metadata": msg.metadata_,
        "is_read": msg.is_read,
        "sent_at": msg.sent_at,
        "attachments": [],
    }

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

@router.post("/conversations/{conversation_id}/attachments", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
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
    file_bytes = await file.read()

    storage_service = StorageService(db=db)
    upload_res = await storage_service.upload_file(
        current_user=current_user,
        file_bytes=file_bytes,
        content_type=content_type,
        filename=file.filename,
        bucket="chat_attachments",
        purpose="chat_attachment",
        resource_id=str(conversation_id),
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
        expires_in=3600
    )
    return {"signed_url": signed_url, "file_name": attachment.file_name, "mime_type": attachment.mime_type}

@router.get("/presence/{user_id}")
async def get_user_presence(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
):
    return manager.get_presence(str(user_id))

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. Authenticate JWT token
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token subject")
            return
        user_id = UUID(user_id_str)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # 2. Accept and connect socket
    connected = await manager.connect(user_id_str, websocket)
    if not connected:
        return

    service = MessagingService(db)

    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                frame = json.loads(data_str)
            except Exception:
                await websocket.send_text(json.dumps({
                    "version": "1.0",
                    "event": "error",
                    "data": {"code": "INVALID_JSON", "message": "Malformed JSON payload"}
                }))
                continue

            event_type = frame.get("event")
            correlation_id = frame.get("correlation_id")
            event_data = frame.get("data", {})

            # 3. Dispatch incoming WebSocket events
            if event_type == "ping":
                await websocket.send_text(json.dumps({
                    "version": "1.0",
                    "event": "pong",
                    "correlation_id": correlation_id,
                    "data": {}
                }))

            elif event_type in ("typing.started", "typing.stopped"):
                conv_id_str = event_data.get("conversation_id")
                if conv_id_str:
                    try:
                        conv_id = UUID(conv_id_str)
                        # Verify membership
                        part_q = select(ConversationParticipant.user_id).where(
                            ConversationParticipant.conversation_id == conv_id,
                            ConversationParticipant.user_id != user_id,
                            ConversationParticipant.is_active.is_(True)
                        )
                        recipients = list((await db.execute(part_q)).scalars().all())
                        if event_type == "typing.started":
                            manager.handle_typing_start(conv_id_str, user_id_str, recipients)
                        else:
                            manager.handle_typing_stop(conv_id_str, user_id_str, recipients)
                    except Exception:
                        pass

            elif event_type == "message.send":
                try:
                    conv_id_str = event_data.get("conversation_id")
                    content = event_data.get("content", "").strip()
                    idempotency_key = event_data.get("idempotency_key")
                    reply_to_id = UUID(event_data["reply_to_message_id"]) if event_data.get("reply_to_message_id") else None
                    att_ids = [UUID(a) for a in event_data.get("attachment_ids", [])]

                    send_req = SendMessageRequest(
                        conversation_id=UUID(conv_id_str),
                        content=content,
                        message_type=event_data.get("message_type", "text"),
                        idempotency_key=idempotency_key,
                        reply_to_message_id=reply_to_id,
                        attachment_ids=att_ids,
                        metadata=event_data.get("metadata", {})
                    )
                    await service.send_message(user_id, send_req)
                except Exception as err:
                    await websocket.send_text(json.dumps({
                        "version": "1.0",
                        "event": "error",
                        "correlation_id": correlation_id,
                        "data": {"code": "SEND_ERROR", "message": str(err)}
                    }))

            elif event_type == "message.read":
                try:
                    conv_id_str = event_data.get("conversation_id")
                    last_read_id_str = event_data.get("last_read_message_id")
                    if conv_id_str:
                        await service.mark_read(
                            conversation_id=UUID(conv_id_str),
                            user_id=user_id,
                            last_read_message_id=UUID(last_read_id_str) if last_read_id_str else None
                        )
                except Exception:
                    pass

    except WebSocketDisconnect:
        manager.disconnect(user_id_str, websocket)
    except Exception:
        manager.disconnect(user_id_str, websocket)
