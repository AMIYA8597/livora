from typing import List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.modules.messaging.models import Conversation, ConversationParticipant, Message
from app.modules.messaging.schemas import SendMessageRequest, CreateConversationRequest
from app.modules.messaging.websocket import manager
from app.core.exceptions import ForbiddenException

class MessagingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_conversations(self, user_id: UUID) -> List[dict]:
        # Fetch conversations where user is a participant
        subq = (
            select(ConversationParticipant.conversation_id)
            .where(ConversationParticipant.user_id == user_id)
        )
        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants),
                selectinload(Conversation.messages)
            )
            .where(Conversation.id.in_(subq))
            .order_by(Conversation.last_message_at.desc())
        )
        result = await self.db.execute(query)
        convs = result.scalars().all()

        formatted = []
        for c in convs:
            p_ids = [p.user_id for p in c.participants]
            last_msg = c.messages[-1] if c.messages else None
            formatted.append({
                "id": c.id,
                "type": c.type,
                "property_id": c.property_id,
                "participants": p_ids,
                "last_message": {
                    "id": last_msg.id,
                    "conversation_id": last_msg.conversation_id,
                    "sender_id": last_msg.sender_id,
                    "content": last_msg.content,
                    "message_type": last_msg.message_type,
                    "metadata": last_msg.metadata_,
                    "is_read": last_msg.is_read,
                    "sent_at": last_msg.sent_at,
                } if last_msg else None,
                "created_at": c.created_at,
                "last_message_at": c.last_message_at,
            })
        return formatted

    async def get_messages(self, conversation_id: UUID, user_id: UUID, limit: int = 50) -> List[Message]:
        # Verify user is a participant
        part_check = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
        if not (await self.db.execute(part_check)).scalar_one_or_none():
            raise ForbiddenException("You are not a participant in this conversation")

        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sent_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_conversation(self, creator_id: UUID, req: CreateConversationRequest) -> Conversation:
        all_participants = list(set([creator_id] + req.participant_user_ids))
        conv = Conversation(type=req.type, property_id=req.property_id)
        self.db.add(conv)
        await self.db.flush()

        for uid in all_participants:
            self.db.add(ConversationParticipant(conversation_id=conv.id, user_id=uid))

        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def send_message(self, sender_id: UUID, req: SendMessageRequest) -> Message:
        # Verify sender is participant
        part_check = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == req.conversation_id,
            ConversationParticipant.user_id == sender_id,
        )
        if not (await self.db.execute(part_check)).scalar_one_or_none():
            raise ForbiddenException("You are not authorized to send messages to this conversation")

        msg = Message(
            conversation_id=req.conversation_id,
            sender_id=sender_id,
            content=req.content,
            message_type=req.message_type,
            metadata_=req.metadata,
        )
        self.db.add(msg)

        # Update last_message_at
        conv_query = select(Conversation).where(Conversation.id == req.conversation_id)
        conv = (await self.db.execute(conv_query)).scalar_one()
        conv.last_message_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(msg)

        # Broadcast via WebSocket manager to other participants
        parts_query = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == req.conversation_id,
            ConversationParticipant.user_id != sender_id,
        )
        recipient_ids = (await self.db.execute(parts_query)).scalars().all()

        ws_payload = {
            "event": "message_received",
            "data": {
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "sender_id": str(msg.sender_id),
                "content": msg.content,
                "message_type": msg.message_type,
                "metadata": msg.metadata_,
                "sent_at": msg.sent_at.isoformat(),
            }
        }
        await manager.broadcast_to_users(ws_payload, recipient_ids)

        return msg
