export type ConversationType = 'direct' | 'group' | 'property_inquiry';
export type MessageType = 'text' | 'image' | 'property_card' | 'application_update';

export interface MessageDTO {
  id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  message_type: MessageType;
  metadata?: Record<string, unknown>;
  is_read: boolean;
  sent_at: string;
}

export interface ConversationDTO {
  id: string;
  type: ConversationType;
  property_id?: string | null;
  participants: string[];
  last_message?: MessageDTO | null;
  created_at: string;
  last_message_at: string;
}

export interface SendMessageInput {
  conversation_id: string;
  content: string;
  message_type?: MessageType;
  metadata?: Record<string, unknown>;
}

export interface WebSocketEvent<T = unknown> {
  event: 'message_received' | 'user_typing' | 'read_receipt' | 'presence_update';
  data: T;
}
