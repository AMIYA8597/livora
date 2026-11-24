"""
Production-Grade Messaging and Communication Service.
Handles conversation lifecycle, message durability, idempotency, read cursors,
group permissions, moderation blocking, attachments, and real-time dispatch.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
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
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException, BadRequestException
from app.ml.moderation import prescreen
from app.ml.moderation_jobs import ai_moderation_on, queue_message_moderation
from app.workers.outbox import schedule_dispatch

DELETED_TEXT = "This message was deleted."


def attachment_dict(a: Attachment) -> Dict[str, Any]:
    return {
        "id": a.id,
        "conversation_id": a.conversation_id,
        "message_id": a.message_id,
        "uploader_id": a.uploader_id,
        "file_name": a.file_name,
        "file_path": a.file_path,
        "mime_type": a.mime_type,
        "file_size_bytes": a.file_size_bytes,
        "created_at": a.created_at,
    }


def message_dict(m: Message, attachments: Optional[List[Attachment]] = None, include_reply: bool = False) -> Dict[str, Any]:
    """One message as the API returns it. Deleted messages never expose their text."""
    reply = getattr(m, "reply_to", None) if include_reply else None
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender_id": m.sender_id,
        "content": DELETED_TEXT if m.is_deleted else m.content,
        "message_type": m.message_type,
        "idempotency_key": m.idempotency_key,
        "reply_to_message_id": m.reply_to_message_id,
        "reply_to": {
            "id": reply.id,
            "sender_id": reply.sender_id,
            "content": DELETED_TEXT if reply.is_deleted else reply.content,
        } if reply else None,
        "is_edited": m.is_edited,
        "edited_at": m.edited_at,
        "is_deleted": m.is_deleted,
        "deleted_at": m.deleted_at,
        "metadata": m.metadata_ or {},
        "is_read": m.is_read,
        "sent_at": m.sent_at,
        "attachments": [attachment_dict(a) for a in (attachments if attachments is not None else [])],
    }


def jsonable(value: Any) -> Any:
    """UUIDs and datetimes to strings, for realtime payloads."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def is_muted(pref: Optional[ConversationPreference], now: Optional[datetime] = None) -> bool:
    if pref is None or not pref.is_muted:
        return False
    if pref.muted_until is None:
        return True
    return pref.muted_until > (now or datetime.now(timezone.utc))


def _participant_dict(p: ConversationParticipant) -> Dict[str, Any]:
    return {
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
        } if p.user else None,
    }


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
        """Conversations where the user is an active participant, newest first.

        The last message and unread count are computed in SQL. (This used to load every
        message of every conversation into memory just to find the latest one.)
        """
        my_convs = (
            select(ConversationParticipant.conversation_id)
            .where(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.is_active.is_(True),
            )
        )

        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                selectinload(Conversation.preferences),
            )
            .where(Conversation.id.in_(my_convs))
        )
        if status_filter:
            query = query.where(Conversation.status == status_filter)
        query = query.order_by(Conversation.last_message_at.desc())
        convs = (await self.db.execute(query)).scalars().all()
        if not convs:
            return []
        conv_ids = [c.id for c in convs]

        # Latest message per conversation, preferring one that isn't deleted (DISTINCT ON).
        last_q = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.conversation_id.in_(conv_ids))
            .distinct(Message.conversation_id)
            .order_by(Message.conversation_id, Message.is_deleted.asc(), Message.sent_at.desc(), Message.id.desc())
        )
        last_by_conv = {m.conversation_id: m for m in (await self.db.execute(last_q)).scalars().all()}

        # Unread = messages from others, not deleted, sent after the user's read cursor.
        cursor = (
            select(ConversationReadCursor.conversation_id, ConversationReadCursor.last_read_at)
            .where(ConversationReadCursor.user_id == user_id)
            .subquery()
        )
        unread_q = (
            select(Message.conversation_id, func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .outerjoin(cursor, cursor.c.conversation_id == Message.conversation_id)
            .where(
                Message.conversation_id.in_(conv_ids),
                Message.sender_id != user_id,
                Message.is_deleted.is_(False),
                Message.sent_at > func.coalesce(cursor.c.last_read_at, Conversation.created_at),
            )
            .group_by(Message.conversation_id)
        )
        unread_by_conv = dict((await self.db.execute(unread_q)).all())

        formatted = []
        sq = search_query.lower() if search_query else None
        for c in convs:
            p_details = [_participant_dict(p) for p in c.participants if p.is_active]
            last_msg = last_by_conv.get(c.id)
            pref = next((p for p in c.preferences if p.user_id == user_id), None)

            if sq:
                matches_title = c.title and sq in c.title.lower()
                matches_msg = last_msg and not last_msg.is_deleted and sq in last_msg.content.lower()
                matches_name = any(
                    d["user"] and sq in (d["user"]["full_name"] or "").lower()
                    for d in p_details if d["user_id"] != user_id
                )
                if not (matches_title or matches_msg or matches_name):
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
                "participants": [d["user_id"] for d in p_details],
                "participant_details": p_details,
                "last_message": message_dict(last_msg, last_msg.attachments) if last_msg else None,
                "unread_count": int(unread_by_conv.get(c.id, 0)),
                "preferences": {
                    "conversation_id": c.id,
                    "is_muted": pref.is_muted,
                    "muted_until": pref.muted_until,
                    "is_archived": pref.is_archived,
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

        p_details = [_participant_dict(p) for p in conv.participants if p.is_active]
        active_ids = {p.user_id for p in conv.participants if p.is_active}
        # Where everyone else has read up to, so the client can show read receipts.
        read_cursors = [
            {
                "user_id": rc.user_id,
                "last_read_message_id": rc.last_read_message_id,
                "last_read_at": rc.last_read_at,
            }
            for rc in conv.read_cursors
            if rc.user_id != user_id and rc.user_id in active_ids
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
            "read_cursors": read_cursors,
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

    async def attachments_for(self, message_id: UUID) -> List[Attachment]:
        return list((await self.db.execute(
            select(Attachment).where(Attachment.message_id == message_id).order_by(Attachment.created_at)
        )).scalars().all())

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

        # 5. Safety pre-screen (rules, inline). High-risk messages carry a warning for the
        # recipients right away; anything not clear is re-checked by AI moderation in the worker
        # (app/ml/moderation.py), which can confirm, add or lift the warning.
        screen = prescreen(req.content)
        if screen.level == "high" and screen.warning:
            req.metadata["safety_warning"] = screen.warning
            req.metadata["moderation"] = {"label": "pending_review", "source": "rules"}

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

        # Outbox event, processed after a delay: recipients who still haven't read the message
        # by then get an email (see workers/outbox.py). No message text is stored here.
        self.db.add(OutboxEvent(
            event_type="message.created",
            payload={
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "sender_id": str(msg.sender_id),
                "recipient_ids": [str(r) for r in recipient_ids],
                "sent_at": msg.sent_at.isoformat(),
            },
            status="pending",
            next_attempt_at=now_dt + timedelta(minutes=settings.CHAT_UNREAD_EMAIL_DELAY_MINUTES),
        ))

        needs_review = screen.level == "high" or (screen.level == "review" and ai_moderation_on())
        if needs_review:
            queue_message_moderation(self.db, msg.id)

        await self.db.commit()
        await self.db.refresh(msg)
        if needs_review:
            schedule_dispatch()

        # 8. Real-time broadcast to participants, including any attachments.
        attachments = await self.attachments_for(msg.id)
        event_payload = jsonable({**message_dict(msg, attachments), "status": "sent"})
        await manager.broadcast_to_users(
            event_type="message.created",
            data=event_payload,
            user_ids=[sender_id] + recipient_ids
        )

        # 9. In-app notification for recipients who haven't muted the conversation.
        prefs = {
            p.user_id: p for p in (await self.db.execute(
                select(ConversationPreference).where(
                    ConversationPreference.conversation_id == conv.id,
                    ConversationPreference.user_id.in_(recipient_ids),
                )
            )).scalars().all()
        } if recipient_ids else {}
        notif_service = NotificationService(self.db)
        for r_id in recipient_ids:
            if is_muted(prefs.get(r_id), now_dt):
                continue
            try:
                await notif_service.create_notification(
                    user_id=r_id,
                    title="New message",
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
        # An edit can turn a harmless message into a risky one: screen it again.
        screen = prescreen(req.content)
        # The old verdict was about the old text. Rules apply at once, as on send; the worker
        # (when queued) replaces this with its own decision.
        meta = {k: v for k, v in (msg.metadata_ or {}).items() if k not in ("safety_warning", "moderation")}
        if screen.level == "high":
            meta["safety_warning"] = screen.warning
            meta["moderation"] = {"label": "pending_review", "source": "rules"}
        msg.metadata_ = meta
        needs_review = screen.level == "high" or (screen.level == "review" and ai_moderation_on())
        if needs_review:
            queue_message_moderation(self.db, msg.id)
        await self.db.commit()
        await self.db.refresh(msg)
        if needs_review:
            schedule_dispatch()

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
                "safety_warning": (msg.metadata_ or {}).get("safety_warning"),
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
        """Move the user's read cursor forward and tell the other participants.

        Only active participants can mark a conversation read, the message must belong to it,
        and the cursor never moves backwards (e.g. when an older page is loaded).
        """
        rows = (await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.is_active.is_(True),
            )
        )).scalars().all()
        if user_id not in rows:
            raise ForbiddenException("You are not a participant in this conversation")
        recipients = [uid for uid in rows if uid != user_id]

        target_sent_at = None
        if last_read_message_id is not None:
            target_sent_at = (await self.db.execute(
                select(Message.sent_at).where(
                    Message.id == last_read_message_id,
                    Message.conversation_id == conversation_id,
                )
            )).scalar_one_or_none()
            if target_sent_at is None:
                raise NotFoundException("Message not found in this conversation")

        cursor = (await self.db.execute(
            select(ConversationReadCursor).where(
                ConversationReadCursor.conversation_id == conversation_id,
                ConversationReadCursor.user_id == user_id,
            )
        )).scalar_one_or_none()
        now_dt = datetime.now(timezone.utc)

        if cursor is None:
            cursor = ConversationReadCursor(
                conversation_id=conversation_id,
                user_id=user_id,
                last_read_message_id=last_read_message_id,
                last_read_at=now_dt,
            )
            self.db.add(cursor)
        else:
            if cursor.last_read_message_id and target_sent_at is not None:
                current_sent_at = (await self.db.execute(
                    select(Message.sent_at).where(Message.id == cursor.last_read_message_id)
                )).scalar_one_or_none()
                if current_sent_at is not None and target_sent_at < current_sent_at:
                    return  # already read further than this
            if last_read_message_id is not None:
                cursor.last_read_message_id = last_read_message_id
            cursor.last_read_at = now_dt

        await self.db.commit()

        await manager.broadcast_to_users(
            event_type="message.read",
            data={
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "last_read_message_id": str(cursor.last_read_message_id) if cursor.last_read_message_id else None,
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
