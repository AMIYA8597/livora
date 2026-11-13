import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class MessageBase(BaseModel):
    content: str
    message_type: str = "text"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SendMessageRequest(MessageBase):
    conversation_id: uuid.UUID

class MessageResponse(MessageBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    is_read: bool
    sent_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ConversationResponse(BaseModel):
    id: uuid.UUID
    type: str
    property_id: Optional[uuid.UUID] = None
    participants: List[uuid.UUID] = []
    last_message: Optional[MessageResponse] = None
    created_at: datetime
    last_message_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CreateConversationRequest(BaseModel):
    participant_user_ids: List[uuid.UUID]
    type: str = "direct"
    property_id: Optional[uuid.UUID] = None
