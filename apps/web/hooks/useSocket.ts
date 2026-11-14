"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { MessageDTO, WebSocketEnvelope } from "@flatmate/contracts";

export interface SocketCallbacks {
  onMessageCreated?: (msg: MessageDTO) => void;
  onMessageUpdated?: (data: { id: string; conversation_id: string; content: string; is_edited: boolean; edited_at: string }) => void;
  onMessageDeleted?: (data: { id: string; conversation_id: string; is_deleted: boolean; deleted_at: string }) => void;
  onMessageRead?: (data: { conversation_id: string; user_id: string; last_read_message_id?: string; read_at: string }) => void;
  onTypingStarted?: (data: { conversation_id: string; user_id: string }) => void;
  onTypingStopped?: (data: { conversation_id: string; user_id: string }) => void;
  onPresenceChanged?: (data: { user_id: string; status: string; last_seen_at?: string }) => void;
  onNotificationCreated?: (notif: any) => void;
  onConversationUpdated?: (data: any) => void;
}

export function useSocket(callbacks?: SocketCallbacks | ((msg: MessageDTO) => void)) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isUnmountedRef = useRef(false);

  // Normalize callbacks
  const cbRef = useRef<SocketCallbacks>({});
  useEffect(() => {
    if (typeof callbacks === "function") {
      cbRef.current = { onMessageCreated: callbacks };
    } else if (callbacks) {
      cbRef.current = callbacks;
    }
  }, [callbacks]);

  const connect = useCallback(() => {
    if (typeof window === "undefined" || isUnmountedRef.current) return;

    const token = localStorage.getItem("flatmate_access_token") || localStorage.getItem("token");
    if (!token) return;

    // Clean up existing socket
    if (socketRef.current) {
      try {
        socketRef.current.close();
      } catch (e) {
        // ignore
      }
    }

    const baseWsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/messaging/ws";
    const wsUrl = `${baseWsUrl}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptsRef.current = 0;

      // Start ping heartbeat every 25s
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ version: "1.0", event: "ping", data: {} }));
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const envelope: WebSocketEnvelope<any> = JSON.parse(event.data);
        const { event: eventType, data } = envelope;

        if (eventType === "message.created" || envelope.event === ("message_received" as any)) {
          cbRef.current.onMessageCreated?.(data);
        } else if (eventType === "message.updated") {
          cbRef.current.onMessageUpdated?.(data);
        } else if (eventType === "message.deleted") {
          cbRef.current.onMessageDeleted?.(data);
        } else if (eventType === "message.read") {
          cbRef.current.onMessageRead?.(data);
        } else if (eventType === "typing.started") {
          cbRef.current.onTypingStarted?.(data);
        } else if (eventType === "typing.stopped") {
          cbRef.current.onTypingStopped?.(data);
        } else if (eventType === "presence.changed") {
          cbRef.current.onPresenceChanged?.(data);
        } else if (eventType === "notification.created") {
          cbRef.current.onNotificationCreated?.(data);
        } else if (eventType === "conversation.updated") {
          cbRef.current.onConversationUpdated?.(data);
        }
      } catch (err) {
        console.error("WebSocket message parsing error:", err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

      if (!isUnmountedRef.current) {
        // Exponential backoff with jitter: min 1s, max 15s
        const attempts = reconnectAttemptsRef.current;
        const delay = Math.min(1000 * Math.pow(1.5, attempts) + Math.random() * 500, 15000);
        reconnectAttemptsRef.current += 1;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    isUnmountedRef.current = false;
    connect();

    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [connect]);

  const sendEvent = useCallback((event: string, data: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        version: "1.0",
        event,
        timestamp: new Date().toISOString(),
        data,
      }));
    }
  }, []);

  const startTyping = useCallback((conversationId: string) => {
    sendEvent("typing.started", { conversation_id: conversationId });
  }, [sendEvent]);

  const stopTyping = useCallback((conversationId: string) => {
    sendEvent("typing.stopped", { conversation_id: conversationId });
  }, [sendEvent]);

  const markRead = useCallback((conversationId: string, lastReadMessageId?: string) => {
    sendEvent("message.read", {
      conversation_id: conversationId,
      last_read_message_id: lastReadMessageId,
    });
  }, [sendEvent]);

  return { isConnected, sendEvent, startTyping, stopTyping, markRead };
}
