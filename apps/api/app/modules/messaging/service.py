"""
Production-Grade Messaging and Communication Service.
Handles conversation lifecycle, message durability, idempotency, read cursors,
group permissions, moderation blocking, attachments, and real-time dispatch.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.modules.messaging.models import (
    Conversation, ConversationParticipant, Message, Attachment,
    ConversationReadCursor, ConversationPreference, OutboxEvent
)
from app.modules.messaging.schemas import (
    SendMessageRequest, CreateConversationRequest, EditMessageRequest,
    ConversationPreferenceRequest, AddParticipantRequest
)
from app.modules.messaging.websocket import manager
from app.modules.moderation.models import UserBlock
from app.modules.notifications.service import NotificationService
from app.core.exceptions import ForbiddenException, NotFoundException, BadRequestException

class MessagingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check_blocked(self, user_a: UUID, user_b: UUID) -> bool:
        """Check if either user has blocked the other."""
        query = select(UserBlock).where(
            or_(
                and_(UserBlock.user_id == user_a, UserBlock.blocked_user_id == user_b),
                and_(UserBlock.user_id == user_b, UserBlock.blocked_user_id == user_a),
            )
        )
        res = await self.db.execute(query)
        return res.scalar_one_or_none() is not None

    async def list_conversations(
        self,
        user_id: UUID,
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[dict]:
        """Fetch all conversations where user is an active participant."""
        # Find active conversation IDs for user
        subq = (
            select(ConversationParticipant.conversation_id)
            .where(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.is_active.is_(True)
            )
        )

        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                selectinload(Conversation.messages).selectinload(Message.attachments),
                selectinload(Conversation.preferences),
                selectinload(Conversation.read_cursors),
            )
            .where(Conversation.id.in_(subq))
        )

        if status_filter:
            query = query.where(Conversation.status == status_filter)

        query = query.order_by(Conversation.last_message_at.desc())
        result = await self.db.execute(query)
        convs = result.scalars().all()

        formatted = []
        for c in convs:
            # Participant details
            p_details = []
            p_ids = []
            for p in c.participants:
                if p.is_active:
                    p_ids.append(p.user_id)
                    p_details.append({
                        "id": p.id,
                        "conversation_id": p.conversation_id,
                        "user_id": p.user_id,
                        "role": p.role,
                        "joined_at": p.joined_at,
                        "left_at": p.left_at,
                        "is_active": p.is_active,
                        "user": {
                            "id": p.user.id,
                            "full_name": getattr(p.user, "full_name", "User"),
                            "avatar_url": getattr(p.user, "avatar_url", None),
                            "is_verified": getattr(p.user, "is_verified", False),
                            "role": getattr(p.user, "role", "user"),
                        } if p.user else None
                    })

            # Last non-deleted message
            active_messages = [m for m in c.messages if not m.is_deleted]
            last_msg = active_messages[-1] if active_messages else (c.messages[-1] if c.messages else None)

            # Read cursor & unread count
            user_cursor = next((rc for rc in c.read_cursors if rc.user_id == user_id), None)
            last_read_at = user_cursor.last_read_at if user_cursor else c.created_at

            unread_count = sum(
                1 for m in c.messages
                if m.sent_at > last_read_at and m.sender_id != user_id and not m.is_deleted
            )

            # User preference
            pref = next((p for p in c.preferences if p.user_id == user_id), None)

            # Optional search filtering
            if search_query:
                sq = search_query.lower()
                matches_title = c.title and sq in c.title.lower()
                matches_msg = last_msg and sq in last_msg.content.lower()
                if not (matches_title or matches_msg):
                    continue

            formatted.append({
                "id": c.id,
                "type": c.type,
                "title": c.title,
                "property_id": c.property_id,
                "application_id": c.application_id,
                "group_id": c.group_id,
                "flatmate_match_id": c.flatmate_match_id,
                "status": c.status,
                "context_metadata": c.context_metadata or {},
                "participants": p_ids,
                "participant_details": p_details,
                "last_message": {
                    "id": last_msg.id,
                    "conversation_id": last_msg.conversation_id,
                    "sender_id": last_msg.sender_id,
                    "content": last_msg.content if not last_msg.is_deleted else "This message was deleted.",
                    "message_type": last_msg.message_type,
                    "metadata": last_msg.metadata_,
                    "is_read": last_msg.is_read,
                    "is_edited": last_msg.is_edited,
                    "is_deleted": last_msg.is_deleted,
                    "sent_at": last_msg.sent_at,
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
                        } for a in getattr(last_msg, "attachments", [])
                    ]
                } if last_msg else None,
                "unread_count": unread_count,
                "preferences": {
                    "conversation_id": c.id,
                    "is_muted": pref.is_muted if pref else False,
                    "muted_until": pref.muted_until if pref else None,
                    "is_archived": pref.is_archived if pref else False,
                } if pref else None,
                "created_at": c.created_at,
                "last_message_at": c.last_message_at,
            })
        return formatted

    async def get_conversation(self, conversation_id: UUID, user_id: UUID) -> dict:
        """Fetch single conversation with full participant details."""
        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                selectinload(Conversation.preferences),
                selectinload(Conversation.read_cursors),
            )
            .where(Conversation.id == conversation_id)
        )
        res = await self.db.execute(query)
        conv = res.scalar_one_or_none()
        if not conv:
            raise NotFoundException("Conversation not found")

        # Verify active participant
        user_part = next((p for p in conv.participants if p.user_id == user_id and p.is_active), None)
        if not user_part:
            raise ForbiddenException("You are not an active participant in this conversation")

        p_details = [
            {
                "id": p.id,
                "conversation_id": p.conversation_id,
                "user_id": p.user_id,
                "role": p.role,
                "joined_at": p.joined_at,
                "left_at": p.left_at,
                "is_active": p.is_active,
                "user": {
                    "id": p.user.id,
                    "full_name": getattr(p.user, "full_name", "User"),
                    "avatar_url": getattr(p.user, "avatar_url", None),
                    "is_verified": getattr(p.user, "is_verified", False),
                    "role": getattr(p.user, "role", "user"),
                } if p.user else None
            } for p in conv.participants if p.is_active
        ]

        pref = next((p for p in conv.preferences if p.user_id == user_id), None)

        return {
            "id": conv.id,
            "type": conv.type,
            "title": conv.title,
            "property_id": conv.property_id,
            "application_id": conv.application_id,
            "group_id": conv.group_id,
            "flatmate_match_id": conv.flatmate_match_id,
            "status": conv.status,
            "context_metadata": conv.context_metadata or {},
            "participants": [p["user_id"] for p in p_details],
            "participant_details": p_details,
            "preferences": {
                "conversation_id": conv.id,
                "is_muted": pref.is_muted if pref else False,
                "muted_until": pref.muted_until if pref else None,
                "is_archived": pref.is_archived if pref else False,
            } if pref else None,
            "created_at": conv.created_at,
            "last_message_at": conv.last_message_at,
        }

    async def create_conversation(self, creator_id: UUID, req: CreateConversationRequest) -> Conversation:
        """
        Create a new conversation or return existing matching conversation to enforce uniqueness.
        Enforces blocking checks and business context rules.
        """
        target_uids = list(set([creator_id] + req.participant_user_ids))

        # 1. Moderation & Safety check: Cannot start conversation if blocked
        for other_id in req.participant_user_ids:
            if other_id != creator_id:
                if await self._check_blocked(creator_id, other_id):
                    raise ForbiddenException("Cannot initiate conversation: you are blocked or have blocked a participant.")

        # 2. Check for existing unique conversation
        if req.type == "direct" and len(target_uids) == 2:
            other_uid = [u for u in target_uids if u != creator_id][0]
            # Find direct conversation containing both users
            existing_q = (
                select(Conversation)
                .join(ConversationParticipant)
                .where(
                    Conversation.type == "direct",
                    Conversation.status == "active",
                    ConversationParticipant.user_id.in_([creator_id, other_uid])
                )
                .group_by(Conversation.id)
                .having(func.count(ConversationParticipant.user_id) == 2)
            )
            existing_conv = (await self.db.execute(existing_q)).scalars().first()
            if existing_conv:
                return existing_conv

        elif req.type == "property_inquiry" and req.property_id and len(target_uids) == 2:
            other_uid = [u for u in target_uids if u != creator_id][0]
            existing_q = (
                select(Conversation)
                .join(ConversationParticipant)
                .where(
                    Conversation.type == "property_inquiry",
                    Conversation.property_id == req.property_id,
                    Conversation.status == "active",
                    ConversationParticipant.user_id.in_([creator_id, other_uid])
                )
                .group_by(Conversation.id)
                .having(func.count(ConversationParticipant.user_id) == 2)
            )
            existing_conv = (await self.db.execute(existing_q)).scalars().first()
            if existing_conv:
                return existing_conv

        elif req.type == "application_linked" and req.application_id:
            existing_q = select(Conversation).where(
                Conversation.type == "application_linked",
                Conversation.application_id == req.application_id,
                Conversation.status == "active"
            )
            existing_conv = (await self.db.execute(existing_q)).scalars().first()
            if existing_conv:
                return existing_conv

        # 3. Create new conversation
        conv = Conversation(
            type=req.type,
            title=req.title,
            property_id=req.property_id,
            application_id=req.application_id,
            group_id=req.group_id,
            flatmate_match_id=req.flatmate_match_id,
            status="active",
            context_metadata=req.context_metadata or {},
            created_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        self.db.add(conv)
        await self.db.flush()

        # Add participants
        for uid in target_uids:
            role = "admin" if (req.type == "group" and uid == creator_id) else "member"
            self.db.add(ConversationParticipant(
                conversation_id=conv.id,
                user_id=uid,
                role=role,
                is_active=True,
                joined_at=datetime.now(timezone.utc)
            ))
            # Initialize read cursor
            self.db.add(ConversationReadCursor(
                conversation_id=conv.id,
                user_id=uid,
                last_read_at=datetime.now(timezone.utc)
            ))

        await self.db.commit()
        await self.db.refresh(conv)

        # Broadcast conversation.updated to all participants
        await manager.broadcast_to_users(
            event_type="conversation.updated",
            data={
                "conversation_id": str(conv.id),
                "type": conv.type,
                "title": conv.title,
                "status": conv.status,
            },
            user_ids=target_uids
        )

        return conv

    async def get_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int = 50,
        before_id: Optional[UUID] = None
    ) -> List[Message]:
        """
        Fetch the most recent `limit` messages (older than `before_id` when paging back),
        returned in chronological order.
        """
        # 1. Authorize active membership
        part_check = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
            ConversationParticipant.is_active.is_(True),
        )
        if not (await self.db.execute(part_check)).scalar_one_or_none():
            raise ForbiddenException("You are not a participant in this conversation")

        query = (
            select(Message)
            .options(
                selectinload(Message.reply_to),
                selectinload(Message.attachments),
            )
            .where(Message.conversation_id == conversation_id)
        )

        if before_id:
            # Find timestamp of before_id
            target_msg_q = select(Message.sent_at).where(Message.id == before_id)
            target_sent_at = (await self.db.execute(target_msg_q)).scalar_one_or_none()
            if target_sent_at:
                query = query.where(Message.sent_at < target_sent_at)

        # Newest-first + LIMIT selects the latest page; reverse so the client renders oldest → newest.
        query = query.order_by(Message.sent_at.desc(), Message.id.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(reversed(result.scalars().all()))

    async def send_message(self, sender_id: UUID, req: SendMessageRequest) -> Message:
        """
        Durable message persistence with idempotency, safety moderation,
        blocking checks, attachment linking, and real-time event publication.
        """
        # 1. Authorize sender active membership
        part_check = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == req.conversation_id,
            ConversationParticipant.user_id == sender_id,
            ConversationParticipant.is_active.is_(True),
        )
        if not (await self.db.execute(part_check)).scalar_one_or_none():
            raise ForbiddenException("You are not authorized to send messages to this conversation")

        # 2. Check conversation status
        conv_q = select(Conversation).where(Conversation.id == req.conversation_id)
        conv = (await self.db.execute(conv_q)).scalar_one_or_none()
        if not conv:
            raise NotFoundException("Conversation not found")
        if conv.status in ("closed", "disabled"):
            raise ForbiddenException(f"Conversation is {conv.status}")

        # 3. Find other active participants and check blocking
        parts_q = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == req.conversation_id,
            ConversationParticipant.user_id != sender_id,
            ConversationParticipant.is_active.is_(True),
        )
        recipient_ids = list((await self.db.execute(parts_q)).scalars().all())

        for r_id in recipient_ids:
            if await self._check_blocked(sender_id, r_id):
                raise ForbiddenException("Communication blocked by user preferences.")

        # 4. Idempotency Key check: if sent recently, return existing message
        if req.idempotency_key:
            idem_q = select(Message).where(
                Message.conversation_id == req.conversation_id,
                Message.idempotency_key == req.idempotency_key
            )
            existing_msg = (await self.db.execute(idem_q)).scalar_one_or_none()
            if existing_msg:
                return existing_msg

        # 5. Safety check: Rental advance scam heuristic
        content_lower = req.content.lower()
        if "advance" in content_lower and ("token" in content_lower or "rent" in content_lower or "deposit" in content_lower) and "before visit" in content_lower:
            req.metadata["safety_warning"] = "Suspicious rental advance payment request detected"

        # 6. Validate reply-to if specified
        if req.reply_to_message_id:
            reply_q = select(Message).where(
                Message.id == req.reply_to_message_id,
                Message.conversation_id == req.conversation_id
            )
            if not (await self.db.execute(reply_q)).scalar_one_or_none():
                req.reply_to_message_id = None

        # 7. Create durable message
        now_dt = datetime.now(timezone.utc)
        msg = Message(
            conversation_id=req.conversation_id,
            sender_id=sender_id,
            content=req.content,
            message_type=req.message_type,
            idempotency_key=req.idempotency_key,
            reply_to_message_id=req.reply_to_message_id,
            metadata_=req.metadata,
            is_read=False,
            sent_at=now_dt,
        )
        self.db.add(msg)
        await self.db.flush()

        # Link attachments if supplied
        if req.attachment_ids:
            att_update = (
                update(Attachment)
                .where(
                    Attachment.id.in_(req.attachment_ids),
                    Attachment.conversation_id == req.conversation_id,
                    Attachment.uploader_id == sender_id,
                )
                .values(message_id=msg.id)
            )
            await self.db.execute(att_update)

        # Update conversation last_message_at
        conv.last_message_at = now_dt

        # Update sender read cursor
        cursor_q = select(ConversationReadCursor).where(
            ConversationReadCursor.conversation_id == req.conversation_id,
            ConversationReadCursor.user_id == sender_id,
        )
        sender_cursor = (await self.db.execute(cursor_q)).scalar_one_or_none()
        if sender_cursor:
            sender_cursor.last_read_message_id = msg.id
            sender_cursor.last_read_at = now_dt
        else:
            self.db.add(ConversationReadCursor(
                conversation_id=req.conversation_id,
                user_id=sender_id,
                last_read_message_id=msg.id,
                last_read_at=now_dt,
            ))

        # Add outbox event for at-least-once distributed delivery
        outbox = OutboxEvent(
            event_type="message.created",
            payload={
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "sender_id": str(msg.sender_id),
                "content": msg.content,
                "message_type": msg.message_type,
                "idempotency_key": msg.idempotency_key,
                "reply_to_message_id": str(msg.reply_to_message_id) if msg.reply_to_message_id else None,
                "sent_at": msg.sent_at.isoformat(),
            },
            status="pending"
        )
        self.db.add(outbox)

        await self.db.commit()
        await self.db.refresh(msg)

        # 8. Real-time broadcast to participants via WebSocket manager
        event_payload = {
            "id": str(msg.id),
            "conversation_id": str(msg.conversation_id),
            "sender_id": str(msg.sender_id),
            "content": msg.content,
            "message_type": msg.message_type,
            "idempotency_key": msg.idempotency_key,
            "reply_to_message_id": str(msg.reply_to_message_id) if msg.reply_to_message_id else None,
            "sent_at": msg.sent_at.isoformat(),
            "status": "sent",
        }
        await manager.broadcast_to_users(
            event_type="message.created",
            data=event_payload,
            user_ids=[sender_id] + recipient_ids
        )

        # 9. Deliver in-app notification to offline or unmuted recipients
        notif_service = NotificationService(self.db)
        for r_id in recipient_ids:
            try:
                await notif_service.create_notification(
                    user_id=r_id,
                    title="New Message",
                    body=req.content[:100],
                    notification_type="new_message",
                    reference_id=conv.id
                )
            except Exception:
                pass

        return msg

    async def edit_message(self, message_id: UUID, user_id: UUID, req: EditMessageRequest) -> Message:
        """Edit message content by author."""
        query = select(Message).where(Message.id == message_id)
        msg = (await self.db.execute(query)).scalar_one_or_none()
        if not msg:
            raise NotFoundException("Message not found")
        if msg.sender_id != user_id:
            raise ForbiddenException("You cannot edit a message you did not author")
        if msg.is_deleted:
            raise BadRequestException("Cannot edit a deleted message")

        msg.content = req.content
        msg.is_edited = True
        msg.edited_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(msg)

        # Broadcast message.updated
        parts_q = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == msg.conversation_id,
            ConversationParticipant.is_active.is_(True)
        )
        recipients = list((await self.db.execute(parts_q)).scalars().all())

        await manager.broadcast_to_users(
            event_type="message.updated",
            data={
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "content": msg.content,
                "is_edited": True,
                "edited_at": msg.edited_at.isoformat(),
            },
            user_ids=recipients
        )
        return msg

    async def delete_message(self, message_id: UUID, user_id: UUID) -> Message:
        """Soft delete a message."""
        query = select(Message).where(Message.id == message_id)
        msg = (await self.db.execute(query)).scalar_one_or_none()
        if not msg:
            raise NotFoundException("Message not found")
        if msg.sender_id != user_id:
            # Check if caller is group admin
            admin_check = select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == msg.conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.role == "admin",
                ConversationParticipant.is_active.is_(True)
            )
            if not (await self.db.execute(admin_check)).scalar_one_or_none():
                raise ForbiddenException("You are not authorized to delete this message")

        msg.is_deleted = True
        msg.deleted_at = datetime.now(timezone.utc)
        msg.content = "This message was deleted."
        await self.db.commit()
        await self.db.refresh(msg)

        # Broadcast message.deleted
        parts_q = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == msg.conversation_id,
            ConversationParticipant.is_active.is_(True)
        )
        recipients = list((await self.db.execute(parts_q)).scalars().all())

        await manager.broadcast_to_users(
            event_type="message.deleted",
            data={
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "is_deleted": True,
                "deleted_at": msg.deleted_at.isoformat(),
            },
            user_ids=recipients
        )
        return msg

    async def mark_read(self, conversation_id: UUID, user_id: UUID, last_read_message_id: Optional[UUID] = None) -> None:
        """Update read cursor for user and broadcast message.read."""
        cursor_q = select(ConversationReadCursor).where(
            ConversationReadCursor.conversation_id == conversation_id,
            ConversationReadCursor.user_id == user_id,
        )
        cursor = (await self.db.execute(cursor_q)).scalar_one_or_none()
        now_dt = datetime.now(timezone.utc)

        if cursor:
            cursor.last_read_message_id = last_read_message_id
            cursor.last_read_at = now_dt
        else:
            cursor = ConversationReadCursor(
                conversation_id=conversation_id,
                user_id=user_id,
                last_read_message_id=last_read_message_id,
                last_read_at=now_dt
            )
            self.db.add(cursor)

        await self.db.commit()

        # Broadcast message.read to other conversation members
        parts_q = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id != user_id,
            ConversationParticipant.is_active.is_(True)
        )
        recipients = list((await self.db.execute(parts_q)).scalars().all())

        await manager.broadcast_to_users(
            event_type="message.read",
            data={
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "last_read_message_id": str(last_read_message_id) if last_read_message_id else None,
                "read_at": now_dt.isoformat(),
            },
            user_ids=recipients
        )

    async def update_preferences(
        self,
        conversation_id: UUID,
        user_id: UUID,
        req: ConversationPreferenceRequest
    ) -> ConversationPreference:
        """Update user conversation preferences (mute, archive)."""
        pref_q = select(ConversationPreference).where(
            ConversationPreference.conversation_id == conversation_id,
            ConversationPreference.user_id == user_id,
        )
        pref = (await self.db.execute(pref_q)).scalar_one_or_none()
        now_dt = datetime.now(timezone.utc)

        if not pref:
            pref = ConversationPreference(
                conversation_id=conversation_id,
                user_id=user_id,
                created_at=now_dt,
                updated_at=now_dt
            )
            self.db.add(pref)

        if req.is_muted is not None:
            pref.is_muted = req.is_muted
        if req.muted_until is not None:
            pref.muted_until = req.muted_until
        if req.is_archived is not None:
            pref.is_archived = req.is_archived

        pref.updated_at = now_dt
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def add_participant(self, conversation_id: UUID, actor_id: UUID, req: AddParticipantRequest) -> ConversationParticipant:
        """Add a member to a group conversation (admin only)."""
        conv = (await self.db.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
        if not conv:
            raise NotFoundException("Conversation not found")
        if conv.type != "group":
            raise BadRequestException("Cannot add participants to a non-group conversation")

        # Verify actor is admin
        actor_part = (await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == actor_id,
                ConversationParticipant.role == "admin",
                ConversationParticipant.is_active.is_(True)
            )
        )).scalar_one_or_none()
        if not actor_part:
            raise ForbiddenException("Only group admins can add participants")

        # Check existing
        existing = (await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == req.user_id
            )
        )).scalar_one_or_none()

        now_dt = datetime.now(timezone.utc)
        if existing:
            existing.is_active = True
            existing.role = req.role
            existing.left_at = None
            part = existing
        else:
            part = ConversationParticipant(
                conversation_id=conversation_id,
                user_id=req.user_id,
                role=req.role,
                is_active=True,
                joined_at=now_dt
            )
            self.db.add(part)

        await self.db.commit()
        await self.db.refresh(part)

        # Broadcast member added
        all_parts = list((await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.is_active.is_(True)
            )
        )).scalars().all())

        await manager.broadcast_to_users(
            event_type="conversation.member_added",
            data={
                "conversation_id": str(conversation_id),
                "user_id": str(req.user_id),
                "role": req.role,
                "joined_at": now_dt.isoformat()
            },
            user_ids=all_parts
        )
        return part

    async def remove_participant(self, conversation_id: UUID, actor_id: UUID, target_user_id: UUID) -> bool:
        """Remove a participant or leave a group conversation."""
        conv = (await self.db.execute(select(Conversation).where(Conversation.id == conversation_id))).scalar_one_or_none()
        if not conv:
            raise NotFoundException("Conversation not found")

        # Actor must either be self (leaving) or group admin (removing another)
        if actor_id != target_user_id:
            actor_admin = (await self.db.execute(
                select(ConversationParticipant).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id == actor_id,
                    ConversationParticipant.role == "admin",
                    ConversationParticipant.is_active.is_(True)
                )
            )).scalar_one_or_none()
            if not actor_admin:
                raise ForbiddenException("Only group admins can remove other members")

        target_part = (await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == target_user_id,
                ConversationParticipant.is_active.is_(True)
            )
        )).scalar_one_or_none()
        if not target_part:
            raise NotFoundException("Participant record not found")

        now_dt = datetime.now(timezone.utc)
        target_part.is_active = False
        target_part.left_at = now_dt
        await self.db.commit()

        # Broadcast member removed
        remaining = list((await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.is_active.is_(True)
            )
        )).scalars().all())

        await manager.broadcast_to_users(
            event_type="conversation.member_removed",
            data={
                "conversation_id": str(conversation_id),
                "user_id": str(target_user_id),
                "removed_at": now_dt.isoformat()
            },
            user_ids=remaining + [target_user_id]
        )
        return True
