"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AttachmentDTO, ConversationDTO, MessageDTO } from "@flatmate/contracts";
import { apiClient, NetworkError } from "@/lib/api-client";
import type { UseApiQueryResult } from "@/hooks/useApiQuery";
import { useSocket, type SocketCallbacks } from "@/hooks/useSocket";
import {
  applyIncomingToInbox,
  applyReadEvent,
  mergeFetched,
  otherParticipants,
  upsertMessage,
  withSafetyWarning,
  type Presence,
  type ReadCursor,
  type ReplySuggestions,
} from "./chat-model";

const TYPING_TTL_MS = 6_000;

interface SendPayload {
  conversation_id: string;
  content: string;
  message_type: "text";
  idempotency_key: string;
  reply_to_message_id?: string;
  attachment_ids: string[];
}

interface ActiveState {
  convId: string | null;
  messages: MessageDTO[];
  details: ConversationDTO | null;
  cursors: ReadCursor[];
  error: string | null;
  loaded: boolean;
}

const EMPTY: ActiveState = { convId: null, messages: [], details: null, cursors: [], error: null, loaded: false };

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/**
 * All live state for the messages page: the inbox, the open conversation, read receipts, typing,
 * presence and an outgoing queue.
 *
 * Sending is optimistic. A message that can't reach the server stays in the conversation as
 * "sending"/"Not sent" and is re-sent automatically when the connection comes back (the
 * idempotency key stops duplicates); it can also be retried by hand. After every reconnection the
 * inbox and the open conversation are refetched, so nothing sent while offline is missed.
 */
export function useChat(
  myId: string | undefined,
  activeConvId: string | null,
  /** The page's `/messaging/conversations` query; kept in sync with live events here. */
  inbox: UseApiQueryResult<ConversationDTO[]>,
) {
  const setInbox = inbox.setData;
  const refetchInbox = inbox.refetch;

  const [active, setActive] = useState<ActiveState>(EMPTY);
  const [syncNonce, setSyncNonce] = useState(0);
  const [typing, setTyping] = useState<Record<string, string[]>>({}); // conversation -> user ids
  const [presence, setPresence] = useState<Record<string, Presence>>({});

  const outbox = useRef(new Map<string, SendPayload>()); // idempotency key -> payload
  const typingTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const activeIdRef = useRef(activeConvId);
  useEffect(() => {
    activeIdRef.current = activeConvId;
  }, [activeConvId]);

  // Only the state for the conversation on screen counts; a stale one is ignored.
  const current = active.convId === activeConvId ? active : EMPTY;
  const patchActive = useCallback((convId: string, fn: (s: ActiveState) => ActiveState) => {
    setActive((s) => (s.convId === convId ? fn(s) : s));
  }, []);

  // ------------------------------------------------------------------ sending

  const deliver = useCallback(async (payload: SendPayload) => {
    const { conversation_id: convId, idempotency_key: key } = payload;
    outbox.current.set(key, payload);
    patchActive(convId, (s) => ({
      ...s,
      messages: s.messages.map((m) => (m.idempotency_key === key ? { ...m, status: "sending" } : m)),
    }));
    try {
      const saved = await apiClient<MessageDTO>("/messaging/messages", { method: "POST", body: JSON.stringify(payload) });
      outbox.current.delete(key);
      patchActive(convId, (s) => ({ ...s, messages: upsertMessage(s.messages, { ...saved, status: "sent" }) }));
      setInbox((prev = []) => applyIncomingToInbox(prev, saved, myId, activeIdRef.current).list);
    } catch (err) {
      // Offline or server unreachable: keep it queued for the next reconnect. Anything else
      // (blocked, conversation closed) won't succeed by retrying on its own.
      if (!(err instanceof NetworkError)) outbox.current.delete(key);
      patchActive(convId, (s) => ({
        ...s,
        messages: s.messages.map((m) => (m.idempotency_key === key ? { ...m, status: "failed" } : m)),
        error: err instanceof NetworkError ? null : err instanceof Error ? err.message : "Couldn't send the message",
      }));
    }
  }, [myId, patchActive, setInbox]);

  const flushOutbox = useCallback(() => {
    Array.from(outbox.current.values()).forEach((payload) => void deliver(payload));
  }, [deliver]);

  const send = useCallback((text: string, replyToId?: string, attachments: AttachmentDTO[] = []) => {
    if (!activeConvId || !myId) return;
    const key = newKey();
    const payload: SendPayload = {
      conversation_id: activeConvId,
      content: text,
      message_type: "text",
      idempotency_key: key,
      reply_to_message_id: replyToId,
      attachment_ids: attachments.map((a) => a.id),
    };
    const optimistic: MessageDTO = {
      id: `temp-${key}`,
      conversation_id: activeConvId,
      sender_id: myId,
      content: text,
      message_type: "text",
      idempotency_key: key,
      reply_to_message_id: replyToId,
      is_edited: false,
      is_deleted: false,
      is_read: false,
      sent_at: new Date().toISOString(),
      attachments,
      status: "sending",
    };
    patchActive(activeConvId, (s) => ({ ...s, messages: upsertMessage(s.messages, optimistic), error: null }));
    void deliver(payload);
  }, [activeConvId, myId, patchActive, deliver]);

  const retry = useCallback((messageId: string) => {
    const msg = current.messages.find((m) => m.id === messageId);
    if (!msg?.idempotency_key || !activeConvId) return;
    void deliver(outbox.current.get(msg.idempotency_key) ?? {
      conversation_id: activeConvId,
      content: msg.content,
      message_type: "text",
      idempotency_key: msg.idempotency_key,
      reply_to_message_id: msg.reply_to_message_id ?? undefined,
      attachment_ids: (msg.attachments ?? []).map((a) => a.id),
    });
  }, [current.messages, activeConvId, deliver]);

  // ------------------------------------------------------------------ realtime

  const clearTyping = useCallback((convId: string, userId: string) => {
    const timerKey = `${convId}:${userId}`;
    const t = typingTimers.current.get(timerKey);
    if (t) clearTimeout(t);
    typingTimers.current.delete(timerKey);
    setTyping((prev) => {
      const list = prev[convId];
      if (!list?.includes(userId)) return prev;
      return { ...prev, [convId]: list.filter((u) => u !== userId) };
    });
  }, []);

  const isVisible = () => typeof document === "undefined" || document.visibilityState === "visible";

  const callbacks = useMemo<SocketCallbacks>(() => ({
    onMessageCreated: (msg) => {
      const openId = activeIdRef.current;
      clearTyping(msg.conversation_id, msg.sender_id);
      patchActive(msg.conversation_id, (s) => ({ ...s, messages: upsertMessage(s.messages, { ...msg, status: "sent" }) }));
      let known = true;
      setInbox((prev = []) => {
        const res = applyIncomingToInbox(prev, msg, myId, isVisible() ? openId : null);
        known = res.known;
        return res.list;
      });
      if (!known) refetchInbox(); // a conversation someone just started with me
      if (msg.conversation_id === openId && msg.sender_id !== myId && isVisible()) {
        socketRef.current?.markRead(msg.conversation_id, msg.id);
      }
    },
    onMessageUpdated: (data) => {
      patchActive(data.conversation_id, (s) => ({
        ...s,
        messages: s.messages.map((m) => (m.id === data.id
          ? withSafetyWarning({ ...m, content: data.content, is_edited: true, edited_at: data.edited_at }, data.safety_warning)
          : m)),
      }));
    },
    onMessageModerated: (data) => {
      patchActive(data.conversation_id, (s) => ({
        ...s,
        messages: s.messages.map((m) => (m.id === data.id ? withSafetyWarning(m, data.safety_warning) : m)),
      }));
    },
    onMessageDeleted: (data) => {
      patchActive(data.conversation_id, (s) => ({
        ...s,
        messages: s.messages.map((m) => (m.id === data.id ? { ...m, content: "This message was deleted.", is_deleted: true, attachments: [] } : m)),
      }));
    },
    onMessageRead: (data) => {
      if (data.user_id === myId) return;
      patchActive(data.conversation_id, (s) => ({ ...s, cursors: applyReadEvent(s.cursors, data) }));
    },
    onTypingStarted: ({ conversation_id: convId, user_id: userId }) => {
      if (userId === myId) return;
      setTyping((prev) => {
        const list = prev[convId] ?? [];
        return list.includes(userId) ? prev : { ...prev, [convId]: [...list, userId] };
      });
      const timerKey = `${convId}:${userId}`;
      const old = typingTimers.current.get(timerKey);
      if (old) clearTimeout(old);
      // In case the "stopped" event is lost.
      typingTimers.current.set(timerKey, setTimeout(() => clearTyping(convId, userId), TYPING_TTL_MS));
    },
    onTypingStopped: ({ conversation_id: convId, user_id: userId }) => clearTyping(convId, userId),
    onPresenceChanged: ({ user_id: userId, status, last_seen_at }) => {
      setPresence((prev) => ({ ...prev, [userId]: { status: status === "online" ? "online" : "offline", last_seen_at } }));
    },
    onConversationUpdated: () => refetchInbox(),
    onReconnected: () => {
      refetchInbox();
      setSyncNonce((n) => n + 1);
      flushOutbox();
    },
  }), [myId, patchActive, setInbox, refetchInbox, clearTyping, flushOutbox]);

  const socket = useSocket(callbacks);
  const socketRef = useRef(socket);
  useEffect(() => {
    socketRef.current = socket;
  }, [socket]);

  // Coming back online re-sends queued messages even before the socket reconnects.
  useEffect(() => {
    window.addEventListener("online", flushOutbox);
    return () => window.removeEventListener("online", flushOutbox);
  }, [flushOutbox]);

  // Opening a conversation again after the tab was hidden marks it read.
  useEffect(() => {
    const onVisible = () => {
      const last = active.messages[active.messages.length - 1];
      if (document.visibilityState === "visible" && active.convId && last && last.sender_id !== myId && !last.id.startsWith("temp-")) {
        socketRef.current.markRead(active.convId, last.id);
        setInbox((prev = []) => prev.map((c) => (c.id === active.convId ? { ...c, unread_count: 0 } : c)));
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [active, myId, setInbox]);

  // ------------------------------------------------------------------ loading

  useEffect(() => {
    if (!activeConvId || !myId) return;
    const controller = new AbortController();
    const { signal } = controller;
    Promise.all([
      // The newest page; the API marks the conversation read when it serves it.
      apiClient<MessageDTO[]>(`/messaging/conversations/${activeConvId}/messages`, { signal }),
      apiClient<ConversationDTO>(`/messaging/conversations/${activeConvId}`, { signal }),
    ]).then(
      ([msgs, details]) => {
        if (signal.aborted) return;
        setActive((prev) => ({
          convId: activeConvId,
          messages: prev.convId === activeConvId ? mergeFetched(prev.messages, msgs) : msgs,
          details,
          cursors: (details.read_cursors ?? []) as ReadCursor[],
          error: null,
          loaded: true,
        }));
        setInbox((prev = []) => prev.map((c) => (c.id === activeConvId ? { ...c, unread_count: 0 } : c)));
        // Presence for one-to-one chats; group chats don't show it.
        if (details.type !== "group") {
          for (const p of otherParticipants(details, myId)) {
            apiClient<Presence>(`/messaging/presence/${p.user_id}`, { signal }).then(
              (pr) => setPresence((prev) => ({ ...prev, [p.user_id]: pr })),
              () => undefined,
            );
          }
        }
      },
      (err) => {
        if (signal.aborted) return;
        setActive({ ...EMPTY, convId: activeConvId, error: err instanceof Error ? err.message : "Couldn't load this conversation", loaded: true });
      },
    );
    return () => controller.abort();
  }, [activeConvId, myId, syncNonce, setInbox]);

  // ------------------------------------------------------------------ editing

  const edit = useCallback(async (messageId: string, content: string) => {
    if (!activeConvId) return;
    await apiClient(`/messaging/messages/${messageId}`, { method: "PATCH", body: JSON.stringify({ content }) });
    patchActive(activeConvId, (s) => ({
      ...s,
      messages: s.messages.map((m) => (m.id === messageId ? { ...m, content, is_edited: true } : m)),
    }));
  }, [activeConvId, patchActive]);

  const remove = useCallback(async (messageId: string) => {
    if (!activeConvId) return;
    await apiClient(`/messaging/messages/${messageId}`, { method: "DELETE" });
    patchActive(activeConvId, (s) => ({
      ...s,
      messages: s.messages.map((m) => (m.id === messageId ? { ...m, content: "This message was deleted.", is_deleted: true, attachments: [] } : m)),
    }));
  }, [activeConvId, patchActive]);

  const upload = useCallback((file: File): Promise<AttachmentDTO> => {
    if (!activeConvId) return Promise.reject(new Error("Open a conversation first"));
    const form = new FormData();
    form.append("file", file);
    return apiClient<AttachmentDTO>(`/messaging/conversations/${activeConvId}/attachments`, {
      method: "POST",
      body: form,
      timeoutMs: 60_000,
    });
  }, [activeConvId]);

  /** Reply ideas for the open conversation. Never sent automatically. */
  const suggest = useCallback((): Promise<ReplySuggestions> => {
    if (!activeConvId) return Promise.reject(new Error("Open a conversation first"));
    return apiClient<ReplySuggestions>(`/messaging/conversations/${activeConvId}/suggestions`, { method: "POST" });
  }, [activeConvId]);

  const setMyTyping = useCallback((isTyping: boolean) => {
    if (!activeConvId) return;
    if (isTyping) socket.startTyping(activeConvId);
    else socket.stopTyping(activeConvId);
  }, [activeConvId, socket]);

  const typingIds = activeConvId ? typing[activeConvId] ?? [] : [];

  return {
    active: current,
    typingIds,
    presence,
    socketStatus: socket.status,
    send,
    retry,
    edit,
    remove,
    upload,
    suggest,
    setMyTyping,
    reload: () => setSyncNonce((n) => n + 1),
  };
}
