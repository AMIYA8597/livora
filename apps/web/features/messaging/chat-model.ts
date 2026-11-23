/**
 * Pure chat state rules (no React, no browser APIs) so they can be unit-tested.
 */
import type { ConversationDTO, ConversationParticipantDTO, MessageDTO } from "@flatmate/contracts";

export type DeliveryStatus = "sending" | "sent" | "read" | "failed";

export interface ReadCursor {
  user_id: string;
  last_read_message_id?: string | null;
  last_read_at: string;
}

export type Presence = { status: "online" | "offline"; last_seen_at?: string | null };

export function otherParticipants(conv: Pick<ConversationDTO, "participant_details">, myId?: string): ConversationParticipantDTO[] {
  return (conv.participant_details ?? []).filter((p) => p.user_id !== myId && p.is_active !== false);
}

/** What to call a conversation: the other person's name for one-to-one chats. */
export function conversationTitle(conv: Pick<ConversationDTO, "type" | "title" | "participant_details">, myId?: string): string {
  const others = otherParticipants(conv, myId);
  const names = others.map((p) => p.user?.full_name?.trim()).filter((n): n is string => Boolean(n));
  if (conv.type === "group") {
    if (conv.title) return conv.title;
    if (names.length === 0) return "Group chat";
    return names.length <= 3 ? names.join(", ") : `${names.slice(0, 2).join(", ")} and ${names.length - 2} others`;
  }
  if (names[0]) return names[0];
  return conv.title || (conv.type === "property_inquiry" ? "Property enquiry" : "Conversation");
}

/** A second line under the title: what the chat is about. */
export function conversationSubtitle(conv: Pick<ConversationDTO, "type" | "title" | "participant_details">, myId?: string): string {
  if (conv.type === "group") return `${otherParticipants(conv, myId).length + 1} members`;
  if (conv.type === "property_inquiry") return conv.title && conv.title !== conversationTitle(conv, myId) ? conv.title : "Property enquiry";
  if (conv.type === "application_linked") return "About an application";
  return "Direct message";
}

export function senderName(conv: Pick<ConversationDTO, "participant_details"> | undefined, senderId: string, myId?: string): string {
  if (senderId === myId) return "You";
  const p = conv?.participant_details?.find((x) => x.user_id === senderId);
  return p?.user?.full_name?.trim() || "Former member";
}

/** Timestamps arrive as "…Z" from the browser and "…+00:00" (with microseconds) from the API. */
export const time = (iso: string | null | undefined): number => (iso ? Date.parse(iso) : 0);

function sameMessage(a: MessageDTO, b: MessageDTO): boolean {
  return a.id === b.id || Boolean(a.idempotency_key && a.idempotency_key === b.idempotency_key);
}

/**
 * Insert or replace a message, matching on id or idempotency key (so the server's copy replaces
 * the optimistic one), keeping the list in time order.
 */
export function upsertMessage(list: MessageDTO[], incoming: MessageDTO): MessageDTO[] {
  const idx = list.findIndex((m) => sameMessage(m, incoming));
  if (idx >= 0) {
    const next = list.slice();
    next[idx] = { ...list[idx], ...incoming };
    return next;
  }
  const next = [...list, incoming];
  // Usually already last; only sort when it isn't.
  if (list.length && time(list[list.length - 1].sent_at) > time(incoming.sent_at)) {
    next.sort((a, b) => time(a.sent_at) - time(b.sent_at));
  }
  return next;
}

/**
 * Merge a freshly fetched (newest) page with local state. Keeps local messages the page doesn't
 * have: ones still unsent, and ones newer than the page's newest message, which arrived (by
 * socket or a send that finished) while the request was in flight.
 */
export function mergeFetched(local: MessageDTO[], fetched: MessageDTO[]): MessageDTO[] {
  const newestFetched = fetched.reduce((t, m) => Math.max(t, time(m.sent_at)), 0);
  let merged = fetched.slice();
  for (const m of local) {
    if (fetched.some((f) => sameMessage(f, m))) continue;
    const pending = m.status === "sending" || m.status === "failed";
    if (pending || time(m.sent_at) > newestFetched) merged = upsertMessage(merged, m);
  }
  return merged;
}

/** Delivery status of one of my messages, from the other participants' read positions. */
export function deliveryStatus(msg: MessageDTO, cursors: ReadCursor[]): DeliveryStatus {
  if (msg.status === "sending" || msg.status === "failed") return msg.status;
  const sent = time(msg.sent_at);
  return cursors.some((c) => time(c.last_read_at) >= sent) ? "read" : "sent";
}

/** Apply a `message.read` event to the cursor list. Cursors only move forward. */
export function applyReadEvent(cursors: ReadCursor[], ev: { user_id: string; last_read_message_id?: string | null; read_at: string }): ReadCursor[] {
  const existing = cursors.find((c) => c.user_id === ev.user_id);
  if (existing && time(existing.last_read_at) >= time(ev.read_at)) return cursors;
  const updated: ReadCursor = { user_id: ev.user_id, last_read_message_id: ev.last_read_message_id, last_read_at: ev.read_at };
  return existing ? cursors.map((c) => (c.user_id === ev.user_id ? updated : c)) : [...cursors, updated];
}

/**
 * Reflect an incoming message in the inbox: move the conversation to the top, update its preview
 * and unread count. `known` is false when the conversation isn't in the list yet (refetch it).
 */
export function applyIncomingToInbox(
  convs: ConversationDTO[],
  msg: MessageDTO,
  myId: string | undefined,
  activeId: string | null,
): { list: ConversationDTO[]; known: boolean } {
  const idx = convs.findIndex((c) => c.id === msg.conversation_id);
  if (idx < 0) return { list: convs, known: false };
  const c = convs[idx];
  const fromOther = msg.sender_id !== myId;
  const updated: ConversationDTO = {
    ...c,
    last_message: msg,
    last_message_at: msg.sent_at,
    unread_count: c.id === activeId || !fromOther ? 0 : (c.unread_count ?? 0) + 1,
  };
  return { list: [updated, ...convs.slice(0, idx), ...convs.slice(idx + 1)], known: true };
}

/** "Online", "Last seen 5 min ago", … for a chat header. */
export function presenceLabel(p: Presence | undefined, now: number = Date.now()): string | null {
  if (!p) return null;
  if (p.status === "online") return "Online";
  if (!p.last_seen_at) return null;
  const mins = Math.max(0, Math.round((now - Date.parse(p.last_seen_at)) / 60_000));
  if (mins < 1) return "Last seen just now";
  if (mins < 60) return `Last seen ${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `Last seen ${hours} h ago`;
  return `Last seen ${new Date(p.last_seen_at).toLocaleDateString()}`;
}

export function typingLabel(names: string[]): string | null {
  if (names.length === 0) return null;
  if (names.length === 1) return `${names[0]} is typing…`;
  if (names.length === 2) return `${names[0]} and ${names[1]} are typing…`;
  return "Several people are typing…";
}
