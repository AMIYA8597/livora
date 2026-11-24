export type ConversationType =
  | 'direct'
  | 'property_inquiry'
  | 'flatmate_match'
  | 'application_linked'
  | 'group'
  | 'owner_tenant'
  | 'pg_enquiry';

export type ConversationStatus = 'active' | 'archived' | 'closed' | 'disabled';

export type ParticipantRole = 'admin' | 'member';

export type MessageType = 'text' | 'image' | 'file' | 'property_card' | 'application_update' | 'system';

export interface AttachmentDTO {
  id: string;
  conversation_id: string;
  message_id?: string | null;
  uploader_id: string;
  file_name: string;
  file_path: string;
  mime_type: string;
  file_size_bytes: number;
  signed_url?: string;
  created_at: string;
}

export interface ConversationParticipantDTO {
  id: string;
  conversation_id: string;
  user_id: string;
  role: ParticipantRole;
  joined_at: string;
  left_at?: string | null;
  is_active: boolean;
  user?: {
    id: string;
    full_name?: string;
    avatar_url?: string | null;
    is_verified?: boolean;
    role?: string;
  };
}

export interface ConversationReadCursorDTO {
  conversation_id: string;
  user_id: string;
  last_read_message_id?: string | null;
  last_read_at: string;
}

export interface ConversationPreferenceDTO {
  conversation_id: string;
  is_muted: boolean;
  muted_until?: string | null;
  is_archived: boolean;
}

export interface MessageDTO {
  id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  message_type: MessageType;
  idempotency_key?: string | null;
  reply_to_message_id?: string | null;
  reply_to?: {
    id: string;
    sender_id: string;
    content: string;
  } | null;
  is_edited: boolean;
  edited_at?: string | null;
  is_deleted: boolean;
  deleted_at?: string | null;
  metadata?: Record<string, unknown>;
  is_read: boolean;
  sent_at: string;
  attachments?: AttachmentDTO[];
  status?: 'sending' | 'sent' | 'delivered' | 'read' | 'failed';
}

export interface ConversationDTO {
  id: string;
  type: ConversationType;
  title?: string | null;
  property_id?: string | null;
  application_id?: string | null;
  group_id?: string | null;
  flatmate_match_id?: string | null;
  status: ConversationStatus;
  context_metadata?: Record<string, unknown>;
  participants: string[] | ConversationParticipantDTO[];
  /** Active participants with their public profile (names for titles and senders). */
  participant_details?: ConversationParticipantDTO[];
  /** Other participants' read positions (single-conversation endpoint only), for read receipts. */
  read_cursors?: Omit<ConversationReadCursorDTO, "conversation_id">[];
  last_message?: MessageDTO | null;
  unread_count?: number;
  preferences?: ConversationPreferenceDTO;
  created_at: string;
  last_message_at: string;
}

export interface CreateConversationInput {
  participant_user_ids: string[];
  type?: ConversationType;
  title?: string;
  property_id?: string | null;
  application_id?: string | null;
  group_id?: string | null;
  flatmate_match_id?: string | null;
  context_metadata?: Record<string, unknown>;
}

export interface SendMessageInput {
  conversation_id: string;
  content: string;
  message_type?: MessageType;
  idempotency_key?: string;
  reply_to_message_id?: string | null;
  attachment_ids?: string[];
  metadata?: Record<string, unknown>;
}

export interface EditMessageInput {
  content: string;
}

export interface MarkReadInput {
  last_read_message_id?: string;
}

export interface UpdateConversationPreferenceInput {
  is_muted?: boolean;
  muted_until?: string | null;
  is_archived?: boolean;
}

export type WebSocketEventType =
  | 'connection.ready'
  | 'message.send'
  | 'message.created'
  | 'message.updated'
  | 'message.deleted'
  | 'message.moderated'
  | 'message.delivered'
  | 'message.read'
  | 'typing.started'
  | 'typing.stopped'
  | 'presence.changed'
  | 'conversation.updated'
  | 'conversation.member_added'
  | 'conversation.member_removed'
  | 'notification.created'
  | 'error'
  | 'ping'
  | 'pong';

export interface WebSocketEnvelope<T = unknown> {
  version: '1.0';
  event: WebSocketEventType;
  timestamp: string;
  correlation_id?: string;
  data: T;
}
