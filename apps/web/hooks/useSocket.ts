"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { MessageDTO } from "@flatmate/contracts";

export function useSocket(onMessageReceived?: (msg: MessageDTO) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const token = localStorage.getItem("flatmate_access_token");
    if (!token) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/messaging/ws"}?token=${token}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === "message_received" && onMessageReceived) {
          onMessageReceived(payload.data);
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [onMessageReceived]);

  const sendEvent = useCallback((action: string, data: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ action, data }));
    }
  }, []);

  return { isConnected, sendEvent };
}
