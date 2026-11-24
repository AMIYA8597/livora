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
  /** A phone number or email in the text was hidden: a listing chat before the owner confirmed a visit. */
  contact_hidden?: boolean;
}

/** POST /messaging/listing-chats ("Ask the owner"). */
export interface StartListingChatResponse {
  conversation_id: string;
  /** False when this person already had a chat about this listing (it was reused). */
  created: boolean;
  message_id?: string | null;
}

/**
 * Quick questions on "Ask the owner". The app puts the chosen ones into the first message, so the
 * owner reads plain text and the same list works on web and mobile.
 */
export const LISTING_QUICK_QUESTIONS = [
  { key: 'deposit', label: 'Deposit', text: 'How much is the deposit, and is it fully refundable?' },
  { key: 'bills', label: 'Bills', text: 'Are electricity, water and wifi included in the rent?' },
  { key: 'food', label: 'Food & kitchen', text: 'Is food provided, or can I use the kitchen?' },
  { key: 'visitors', label: 'Visitors', text: 'Are visitors allowed, and is there a curfew?' },
  { key: 'move_in', label: 'Move-in', text: 'When is the earliest I could move in?' },
  { key: 'lock_in', label: 'Lock-in', text: 'Is there a lock-in period or notice period?' },
] as const;

export type ListingQuickQuestionKey = (typeof LISTING_QUICK_QUESTIONS)[number]['key'];

export interface ConversationDTO {
  id: string;
  /** A listing chat before the owner confirmed a visit: phone numbers and emails are hidden. */
  contacts_locked?: boolean;
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
