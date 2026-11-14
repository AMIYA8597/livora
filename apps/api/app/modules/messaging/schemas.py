import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class AttachmentResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: Optional[uuid.UUID] = None
    uploader_id: uuid.UUID
    file_name: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    signed_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ParticipantUser(BaseModel):
    id: uuid.UUID
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    role: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ConversationParticipantResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    left_at: Optional[datetime] = None
    is_active: bool = True
    user: Optional[ParticipantUser] = None
    model_config = ConfigDict(from_attributes=True)

class MessageReplyPreview(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    model_config = ConfigDict(from_attributes=True)

class MessageBase(BaseModel):
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SendMessageRequest(MessageBase):
    conversation_id: uuid.UUID
    idempotency_key: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    attachment_ids: List[uuid.UUID] = Field(default_factory=list)

class EditMessageRequest(BaseModel):
    content: str

class MessageResponse(MessageBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    idempotency_key: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    reply_to: Optional[MessageReplyPreview] = None
    is_edited: bool = False
    edited_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    is_read: bool = False
    sent_at: datetime
    attachments: List[AttachmentResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class ConversationPreferenceResponse(BaseModel):
    conversation_id: uuid.UUID
    is_muted: bool = False
    muted_until: Optional[datetime] = None
    is_archived: bool = False
    model_config = ConfigDict(from_attributes=True)

class ConversationPreferenceRequest(BaseModel):
    is_muted: Optional[bool] = None
    muted_until: Optional[datetime] = None
    is_archived: Optional[bool] = None

class ConversationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: Optional[str] = None
    property_id: Optional[uuid.UUID] = None
    application_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    flatmate_match_id: Optional[uuid.UUID] = None
    status: str = "active"
    context_metadata: Dict[str, Any] = Field(default_factory=dict)
    participants: List[uuid.UUID] = Field(default_factory=list)
    participant_details: List[ConversationParticipantResponse] = Field(default_factory=list)
    last_message: Optional[MessageResponse] = None
    unread_count: int = 0
    preferences: Optional[ConversationPreferenceResponse] = None
    created_at: datetime
    last_message_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CreateConversationRequest(BaseModel):
    participant_user_ids: List[uuid.UUID]
    type: str = "direct"
    title: Optional[str] = None
    property_id: Optional[uuid.UUID] = None
    application_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    flatmate_match_id: Optional[uuid.UUID] = None
    context_metadata: Dict[str, Any] = Field(default_factory=dict)

class MarkReadRequest(BaseModel):
    last_read_message_id: Optional[uuid.UUID] = None

class AddParticipantRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "member"

class RemoveParticipantRequest(BaseModel):
    user_id: uuid.UUID
