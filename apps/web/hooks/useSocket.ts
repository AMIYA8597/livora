"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MessageDTO } from "@flatmate/contracts";
import { API_BASE_URL, refreshAccessToken } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import { socketUrl } from "@/lib/realtime";
import { SocketHub, type Envelope, type SocketLike, type SocketStatus } from "@/lib/socket-hub";

export type { SocketStatus };

export interface SocketCallbacks {
  onMessageCreated?: (msg: MessageDTO) => void;
  onMessageUpdated?: (data: { id: string; conversation_id: string; content: string; is_edited: boolean; edited_at: string; safety_warning?: string | null; contact_hidden?: boolean }) => void;
  /** Moderation finished for a message: show, change or remove its safety warning. */
  onMessageModerated?: (data: { id: string; conversation_id: string; safety_warning?: string | null }) => void;
  onMessageDeleted?: (data: { id: string; conversation_id: string; is_deleted: boolean; deleted_at: string }) => void;
  onMessageRead?: (data: { conversation_id: string; user_id: string; last_read_message_id?: string | null; read_at: string }) => void;
  onTypingStarted?: (data: { conversation_id: string; user_id: string }) => void;
  onTypingStopped?: (data: { conversation_id: string; user_id: string }) => void;
  onPresenceChanged?: (data: { user_id: string; status: string; last_seen_at?: string | null }) => void;
  onNotificationCreated?: (notif: unknown) => void;
  onConversationUpdated?: (data: { conversation_id: string; [key: string]: unknown }) => void;
  /** Fired when the socket comes back after a drop: refetch anything that may have been missed. */
  onReconnected?: () => void;
}

const WS_URL = socketUrl(API_BASE_URL, process.env.NEXT_PUBLIC_WS_URL);

let hub: SocketHub | null = null;

/** The tab's one connection, created on first use. */
function tabHub(): SocketHub {
  hub ??= new SocketHub({
    url: WS_URL,
    createSocket: (url) => new WebSocket(url) as unknown as SocketLike,
    getToken: () => localStorage.getItem("flatmate_access_token"),
    refreshToken: refreshAccessToken,
    isOnline: () => typeof navigator === "undefined" || navigator.onLine !== false,
    watchBrowser: ({ online, offline, visible }) => {
      const onVisible = () => {
        if (document.visibilityState === "visible") visible();
      };
      window.addEventListener("online", online);
      window.addEventListener("offline", offline);
      document.addEventListener("visibilitychange", onVisible);
      return () => {
        window.removeEventListener("online", online);
        window.removeEventListener("offline", offline);
        document.removeEventListener("visibilitychange", onVisible);
      };
    },
  });
  return hub;
}

function dispatch(cb: SocketCallbacks, envelope: Envelope): void {
  const { event, data } = envelope;
  switch (event) {
    case "message.created": cb.onMessageCreated?.(data); break;
    case "message.updated": cb.onMessageUpdated?.(data); break;
    case "message.deleted": cb.onMessageDeleted?.(data); break;
    case "message.moderated": cb.onMessageModerated?.(data); break;
    case "message.read": cb.onMessageRead?.(data); break;
    case "typing.started": cb.onTypingStarted?.(data); break;
    case "typing.stopped": cb.onTypingStopped?.(data); break;
    case "presence.changed": cb.onPresenceChanged?.(data); break;
    case "notification.created": cb.onNotificationCreated?.(data); break;
    case "conversation.updated": cb.onConversationUpdated?.(data); break;
    default: break; // connection.ready, pong, error and future events
  }
}

/**
 * The signed-in user's realtime channel. Every caller in a tab shares one connection
 * (lib/socket-hub.ts), which:
 *
 * - Authenticates with the first frame, so the token never appears in a URL or access log.
 * - Reconnects with backoff, at once when the browser comes back online or the tab is shown, and
 *   renews the access token when the server says it expired (close code 4001).
 * - Treats a connection that has gone quiet (no pong) as dead, e.g. after the laptop slept.
 * - Calls `onReconnected` after every reconnection so the page can catch up on missed events.
 */
export function useSocket(callbacks?: SocketCallbacks) {
  const { isAuthenticated, user } = useAuth();
  const userKey = user?.id ?? "signed-in";
  const [status, setStatus] = useState<SocketStatus>("idle");

  const cbRef = useRef<SocketCallbacks>({});
  useEffect(() => {
    cbRef.current = callbacks ?? {};
  }, [callbacks]);

  useEffect(() => {
    if (!isAuthenticated || typeof window === "undefined") return;
    const unsubscribe = tabHub().subscribe({
      onEnvelope: (envelope) => dispatch(cbRef.current, envelope),
      onStatus: setStatus,
      onReconnected: () => cbRef.current.onReconnected?.(),
    }, userKey);
    return () => {
      unsubscribe();
      setStatus("idle");
    };
  }, [isAuthenticated, userKey]);

  const sendEvent = useCallback(
    (event: string, data: Record<string, unknown>): boolean => hub?.send(event, data) ?? false,
    [],
  );

  const startTyping = useCallback((conversationId: string) => {
    sendEvent("typing.started", { conversation_id: conversationId });
  }, [sendEvent]);

  const stopTyping = useCallback((conversationId: string) => {
    sendEvent("typing.stopped", { conversation_id: conversationId });
  }, [sendEvent]);

  const markRead = useCallback((conversationId: string, lastReadMessageId?: string) => {
    sendEvent("message.read", { conversation_id: conversationId, last_read_message_id: lastReadMessageId });
  }, [sendEvent]);

  return { status, isConnected: status === "open", sendEvent, startTyping, stopTyping, markRead };
}
