"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { MessageDTO, WebSocketEnvelope } from "@flatmate/contracts";
import { API_BASE_URL, refreshAccessToken } from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import {
  HEARTBEAT_INTERVAL_MS,
  closeAction,
  isStale,
  reconnectDelay,
  socketUrl,
} from "@/lib/realtime";

export type SocketStatus = "idle" | "connecting" | "open" | "offline";

export interface SocketCallbacks {
  onMessageCreated?: (msg: MessageDTO) => void;
  onMessageUpdated?: (data: { id: string; conversation_id: string; content: string; is_edited: boolean; edited_at: string; safety_warning?: string | null }) => void;
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

/**
 * The signed-in user's realtime channel.
 *
 * - Authenticates with the first frame, so the token never appears in a URL or access log.
 * - Reconnects with backoff, at once when the browser comes back online or the tab is shown, and
 *   renews the access token when the server says it expired (close code 4001).
 * - Treats a connection that has gone quiet (no pong) as dead, e.g. after the laptop slept.
 * - Calls `onReconnected` after every reconnection so the page can catch up on missed events.
 */
export function useSocket(callbacks?: SocketCallbacks) {
  const { isAuthenticated } = useAuth();
  const [status, setStatus] = useState<SocketStatus>("idle");

  const cbRef = useRef<SocketCallbacks>({});
  useEffect(() => {
    cbRef.current = callbacks ?? {};
  }, [callbacks]);

  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isAuthenticated || typeof window === "undefined") return;

    let disposed = false;
    let attempts = 0;
    let everConnected = false;
    let lastFrameAt = Date.now();
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;

    const clearTimers = () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (heartbeat) clearInterval(heartbeat);
      reconnectTimer = heartbeat = null;
    };

    const scheduleReconnect = (delay: number) => {
      if (disposed) return;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(() => connect(), delay);
    };

    const dispatch = (envelope: WebSocketEnvelope<any>) => {
      const cb = cbRef.current;
      const { event, data } = envelope;
      switch (event) {
        case "connection.ready":
          attempts = 0;
          setStatus("open");
          if (everConnected) cb.onReconnected?.();
          everConnected = true;
          break;
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
        default: break; // pong, error and future events
      }
    };

    function connect() {
      if (disposed) return;
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        setStatus("offline");
        return; // the "online" listener reconnects
      }
      const token = localStorage.getItem("flatmate_access_token");
      if (!token) return;

      const previous = socketRef.current;
      socketRef.current = null; // its close handler must not schedule anything now
      previous?.close(1000, "replaced");
      clearTimers();

      setStatus("connecting");
      const ws = new WebSocket(WS_URL);
      socketRef.current = ws;
      lastFrameAt = Date.now();

      ws.onopen = () => {
        if (socketRef.current !== ws) return;
        ws.send(JSON.stringify({ version: "1.0", event: "auth", data: { token } }));
        heartbeat = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return;
          if (isStale(lastFrameAt, Date.now())) {
            ws.close(4000, "stale"); // dead connection: reconnect
            return;
          }
          ws.send(JSON.stringify({ version: "1.0", event: "ping", data: {} }));
        }, HEARTBEAT_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (socketRef.current !== ws) return;
        lastFrameAt = Date.now();
        try {
          dispatch(JSON.parse(event.data));
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = (event) => {
        if (socketRef.current !== ws) return; // a replaced socket: nothing to do
        socketRef.current = null;
        clearTimers();
        if (disposed) return;
        const action = closeAction(event.code, false);
        if (action === "stop") {
          setStatus("idle");
          return;
        }
        setStatus(typeof navigator !== "undefined" && navigator.onLine === false ? "offline" : "connecting");
        if (action === "refresh") {
          refreshAccessToken().then(
            (newToken) => {
              if (newToken) scheduleReconnect(0); // else signed out: the auth store takes over
            },
            () => scheduleReconnect(reconnectDelay(attempts++)), // offline: keep the session, retry
          );
          return;
        }
        scheduleReconnect(reconnectDelay(attempts++));
      };

      ws.onerror = () => {
        // onclose follows and decides what to do
      };
    }

    const reconnectNow = () => {
      const ws = socketRef.current;
      if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
        attempts = 0;
        connect();
      }
    };
    const onOffline = () => setStatus("offline");
    const onVisible = () => {
      if (document.visibilityState === "visible") reconnectNow();
    };
    window.addEventListener("online", reconnectNow);
    window.addEventListener("offline", onOffline);
    document.addEventListener("visibilitychange", onVisible);

    connect();

    return () => {
      disposed = true;
      clearTimers();
      window.removeEventListener("online", reconnectNow);
      window.removeEventListener("offline", onOffline);
      document.removeEventListener("visibilitychange", onVisible);
      const ws = socketRef.current;
      socketRef.current = null;
      ws?.close(1000, "unmount");
      setStatus("idle");
    };
  }, [isAuthenticated]);

  const sendEvent = useCallback((event: string, data: Record<string, unknown>): boolean => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ version: "1.0", event, timestamp: new Date().toISOString(), data }));
    return true;
  }, []);

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
