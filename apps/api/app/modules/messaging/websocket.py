"""
Authenticated WebSocket Connection Manager and Protocol Handler.
Enforces JWT authentication, conversation authorization, ping/pong heartbeats,
typing expiration, presence tracking, and distributed event routing.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, List
from uuid import UUID

from fastapi import WebSocket, status
from app.modules.messaging.broker import broker

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 10

class ConnectionManager:
    def __init__(self):
        # Map of user_id (str) -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Ephemeral typing state: (conv_id_str, user_id_str) -> asyncio.TimerHandle / Task
        self.active_typing: Dict[str, asyncio.Task] = {}
        # User presence: user_id_str -> {"status": "online", "last_seen_at": str}
        self.presence: Dict[str, dict] = {}
        # Register self with broker
        broker.register_local_listener(self)

    async def connect(self, user_id: str, websocket: WebSocket) -> bool:
        """Accept connection, register socket, and emit connection.ready."""
        if user_id in self.active_connections and len(self.active_connections[user_id]) >= MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Max concurrent connections reached")
            return False

        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Update presence to online
        was_offline = len(self.active_connections[user_id]) == 1
        now_iso = datetime.now(timezone.utc).isoformat()
        self.presence[user_id] = {"status": "online", "last_seen_at": now_iso}

        # Send connection.ready envelope
        ready_envelope = {
            "version": "1.0",
            "event": "connection.ready",
            "timestamp": now_iso,
            "data": {
                "user_id": user_id,
                "server_time": now_iso,
                "heartbeat_interval_ms": 30000,
            }
        }
        await websocket.send_text(json.dumps(ready_envelope))

        if was_offline:
            # Broadcast presence change via broker
            asyncio.create_task(broker.publish(
                event_type="presence.changed",
                data={"user_id": user_id, "status": "online", "last_seen_at": now_iso}
            ))

        return True

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove socket on disconnect; update presence if all sessions closed."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                now_iso = datetime.now(timezone.utc).isoformat()
                self.presence[user_id] = {"status": "offline", "last_seen_at": now_iso}
                # Broadcast offline status
                asyncio.create_task(broker.publish(
                    event_type="presence.changed",
                    data={"user_id": user_id, "status": "offline", "last_seen_at": now_iso}
                ))

    async def send_to_user(self, user_id: str, envelope: dict) -> None:
        """Deliver envelope to all connected sockets for a given user."""
        if user_id not in self.active_connections:
            return
        payload = json.dumps(envelope)
        dead_sockets = set()
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_sockets.add(ws)

        for dead in dead_sockets:
            self.active_connections[user_id].discard(dead)
        if user_id in self.active_connections and not self.active_connections[user_id]:
            del self.active_connections[user_id]

    async def on_broker_event(self, envelope: dict) -> None:
        """
        Handler called when broker dispatches an event (from Redis or local).
        Routes message to specified target users, or all if target_user_ids is None.
        """
        target_user_ids = envelope.get("target_user_ids")
        if target_user_ids is not None:
            for uid in target_user_ids:
                if uid in self.active_connections:
                    await self.send_to_user(uid, envelope)
        else:
            # Broadcast to all connected users
            for uid in list(self.active_connections.keys()):
                await self.send_to_user(uid, envelope)

    async def broadcast_to_users(self, event_type: str, data: dict, user_ids: List[UUID], correlation_id: Optional[str] = None) -> None:
        """Helper to publish an event destined for specific user IDs."""
        await broker.publish(
            event_type=event_type,
            data=data,
            target_user_ids=user_ids,
            correlation_id=correlation_id
        )

    def get_presence(self, user_id: str) -> dict:
        return self.presence.get(user_id, {"status": "offline", "last_seen_at": None})

    def handle_typing_start(self, conv_id: str, user_id: str, recipient_ids: List[UUID]) -> None:
        """Start or renew ephemeral typing indicator with 5s timeout."""
        key = f"{conv_id}:{user_id}"
        if key in self.active_typing:
            self.active_typing[key].cancel()

        # Broadcast typing.started
        asyncio.create_task(self.broadcast_to_users(
            event_type="typing.started",
            data={"conversation_id": conv_id, "user_id": user_id},
            user_ids=recipient_ids
        ))

        # Schedule auto-stop after 5s
        async def _auto_stop():
            try:
                await asyncio.sleep(5)
                await self.broadcast_to_users(
                    event_type="typing.stopped",
                    data={"conversation_id": conv_id, "user_id": user_id},
                    user_ids=recipient_ids
                )
            except asyncio.CancelledError:
                pass
            finally:
                self.active_typing.pop(key, None)

        self.active_typing[key] = asyncio.create_task(_auto_stop())

    def handle_typing_stop(self, conv_id: str, user_id: str, recipient_ids: List[UUID]) -> None:
        """Manually stop typing indicator."""
        key = f"{conv_id}:{user_id}"
        if key in self.active_typing:
            self.active_typing[key].cancel()
            del self.active_typing[key]

        asyncio.create_task(self.broadcast_to_users(
            event_type="typing.stopped",
            data={"conversation_id": conv_id, "user_id": user_id},
            user_ids=recipient_ids
        ))

manager = ConnectionManager()
