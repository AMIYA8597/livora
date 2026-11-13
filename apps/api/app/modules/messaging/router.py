import json
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.modules.users.models import User
from app.modules.messaging.schemas import (
    ConversationResponse, SendMessageRequest, CreateConversationRequest
)
from app.modules.messaging.service import MessagingService
from app.modules.messaging.websocket import manager

router = APIRouter(prefix="/messaging", tags=["Messaging"])

@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    return await service.list_conversations(current_user.id)

@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    req: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    conv = await service.create_conversation(current_user.id, req)
    return {"conversation_id": conv.id}

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MessagingService(db)
    messages = await service.get_messages(conversation_id, current_user.id)
    return [
        {
            "id": m.id,
            "conversation_id": m.conversation_id,
            "sender_id": m.sender_id,
            "content": m.content,
            "message_type": m.message_type,
            "metadata": m.metadata_,
            "is_read": m.is_read,
            "sent_at": m.sent_at,
        }
        for m in messages
    ]

@router.post("/messages")
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
        "metadata": msg.metadata_,
        "is_read": msg.is_read,
        "sent_at": msg.sent_at,
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            data_str = await websocket.receive_text()
            data = json.loads(data_str)
            action = data.get("action")
            # Handle client action (e.g. typing indicator, realtime send)
            if action == "typing":
                # Broadcast typing notice to peer
                pass
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
