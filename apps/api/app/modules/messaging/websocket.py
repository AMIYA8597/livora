"""
Authenticated WebSocket connection manager.

Responsibilities:
  * Track this process's sockets per user and deliver broker events to them.
  * Presence: who is online. Each process knows its own sockets; when Redis is available a
    shared sorted set per user (one member per socket, scored by last heartbeat) lets every
    instance answer "is this user online anywhere?". A socket that stops heartbeating drops
    out after PRESENCE_TTL_SECONDS, so a crashed instance can't leave users "online" forever.
  * Presence changes go only to people who share an active conversation with the user, never
    to every connected client. Going offline is announced after a short grace period, so a
    reconnect (token renewal, flaky network) doesn't flash "offline" to contacts.
  * Ephemeral typing indicators that stop by themselves after a few seconds.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4

from fastapi import WebSocket, status

from app.modules.messaging.broker import broker

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_USER = 10
HEARTBEAT_INTERVAL_MS = 25_000
PRESENCE_TTL_SECONDS = 90
OFFLINE_GRACE_SECONDS = 10
TYPING_TIMEOUT_SECONDS = 5

PRESENCE_KEY = "flatmate:presence:{user_id}"
LAST_SEEN_KEY = "flatmate:last_seen:{user_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def conversation_contacts(user_id: UUID) -> List[UUID]:
    """Users who share at least one active conversation with `user_id`."""
    from sqlalchemy import select
    from sqlalchemy.orm import aliased

    from app.core.database import AsyncSessionLocal
    from app.modules.messaging.models import ConversationParticipant

    me = aliased(ConversationParticipant)
    other = aliased(ConversationParticipant)
    query = (
        select(other.user_id)
        .join(me, me.conversation_id == other.conversation_id)
        .where(
            me.user_id == user_id,
            me.is_active.is_(True),
            other.is_active.is_(True),
            other.user_id != user_id,
        )
        .distinct()
    )
    async with AsyncSessionLocal() as db:
        return list((await db.execute(query)).scalars().all())


async def shares_conversation(user_a: UUID, user_b: UUID) -> bool:
    if user_a == user_b:
        return True
    return user_b in await conversation_contacts(user_a)


class ConnectionManager:
    def __init__(self):
        # user_id (str) -> sockets on this process
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # socket -> its id in the shared presence set
        self._socket_ids: Dict[WebSocket, str] = {}
        # (conversation, user) -> auto-stop task for the typing indicator
        self.active_typing: Dict[str, asyncio.Task] = {}
        # user_id (str) -> pending "went offline" announcement
        self._offline_tasks: Dict[str, asyncio.Task] = {}
        # Local view used when Redis is unavailable: user_id -> {"status", "last_seen_at"}
        self.presence: Dict[str, dict] = {}
        self._background: Set[asyncio.Task] = set()
        broker.register_local_listener(self)

    # ------------------------------------------------------------------ connections

    async def connect(self, user_id: str, websocket: WebSocket) -> bool:
        """Register an authenticated socket and send `connection.ready`.

        Accepts the socket if the endpoint hasn't already (the endpoint accepts first so it can
        read the auth frame). Returns False if the user already has too many open sockets.
        """
        if len(self.active_connections.get(user_id, ())) >= MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Too many open connections")
            return False

        if getattr(websocket, "client_state", None) is None or websocket.client_state.name != "CONNECTED":
            await websocket.accept()

        sockets = self.active_connections.setdefault(user_id, set())
        was_offline_here = not sockets
        sockets.add(websocket)
        socket_id = uuid4().hex
        self._socket_ids[websocket] = socket_id
        now_iso = _now_iso()
        self.presence[user_id] = {"status": "online", "last_seen_at": now_iso}

        await websocket.send_text(json.dumps({
            "version": "1.0",
            "event": "connection.ready",
            "timestamp": now_iso,
            "data": {"user_id": user_id, "server_time": now_iso, "heartbeat_interval_ms": HEARTBEAT_INTERVAL_MS},
        }))

        pending_offline = self._offline_tasks.pop(user_id, None)
        if pending_offline:
            # Reconnected inside the grace period: contacts never saw them leave.
            pending_offline.cancel()
            await self._presence_touch(user_id, socket_id)
        elif was_offline_here:
            was_online_elsewhere = await self._is_online_shared(user_id)
            await self._presence_touch(user_id, socket_id)
            if not was_online_elsewhere:
                self._spawn(self._announce(user_id, "online", now_iso))
        else:
            await self._presence_touch(user_id, socket_id)
        return True

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Forget a socket. If it was the user's last one, announce offline after a grace period."""
        socket_id = self._socket_ids.pop(websocket, None)
        sockets = self.active_connections.get(user_id)
        if sockets is not None:
            sockets.discard(websocket)
            if sockets:
                if socket_id:
                    self._spawn(self._presence_remove(user_id, socket_id))
                return
            del self.active_connections[user_id]

        now_iso = _now_iso()
        self.presence[user_id] = {"status": "offline", "last_seen_at": now_iso}
        if socket_id:
            self._spawn(self._presence_remove(user_id, socket_id, last_seen=now_iso))
        if user_id not in self._offline_tasks:
            self._offline_tasks[user_id] = self._spawn(self._announce_offline_after_grace(user_id, now_iso))

    async def heartbeat(self, user_id: str, websocket: WebSocket) -> None:
        """Called on every client ping: keeps this socket in the shared presence set."""
        socket_id = self._socket_ids.get(websocket)
        if socket_id:
            await self._presence_touch(user_id, socket_id)

    # ------------------------------------------------------------------ delivery

    async def send_to_user(self, user_id: str, envelope: dict) -> None:
        sockets = self.active_connections.get(user_id)
        if not sockets:
            return
        payload = json.dumps(envelope)
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def on_broker_event(self, envelope: dict) -> None:
        """Deliver a broker event to the targeted users connected to this process."""
        targets = envelope.get("target_user_ids")
        if targets is None:
            # Untargeted broadcasts are not used for user data; refuse rather than leak.
            logger.warning("Dropping untargeted realtime event %s", envelope.get("event"))
            return
        outbound = {k: v for k, v in envelope.items() if k != "target_user_ids"}
        for uid in targets:
            if uid in self.active_connections:
                await self.send_to_user(uid, outbound)

    async def broadcast_to_users(
        self, event_type: str, data: dict, user_ids: List[UUID], correlation_id: Optional[str] = None
    ) -> None:
        await broker.publish(event_type=event_type, data=data, target_user_ids=user_ids, correlation_id=correlation_id)

    # ------------------------------------------------------------------ presence

    def get_presence(self, user_id: str) -> dict:
        """This process's view of a user's presence."""
        if self.active_connections.get(user_id):
            return {"status": "online", "last_seen_at": self.presence.get(user_id, {}).get("last_seen_at")}
        return self.presence.get(user_id, {"status": "offline", "last_seen_at": None})

    async def presence_of(self, user_id: str) -> dict:
        """Presence across all instances (Redis), falling back to this process's view."""
        if self.active_connections.get(user_id):
            return {"status": "online", "last_seen_at": None}
        redis = broker.redis
        if redis is not None:
            try:
                if await self._is_online_shared(user_id):
                    return {"status": "online", "last_seen_at": None}
                last_seen = await redis.get(LAST_SEEN_KEY.format(user_id=user_id))
                return {"status": "offline", "last_seen_at": last_seen}
            except Exception as exc:  # noqa: BLE001 - presence is best-effort
                logger.warning("Presence lookup failed: %s", type(exc).__name__)
        return self.get_presence(user_id)

    async def is_online(self, user_id: str) -> bool:
        """Connected to this instance or, through shared presence, to any other."""
        return bool(self.active_connections.get(user_id)) or await self._is_online_shared(user_id)

    async def _is_online_shared(self, user_id: str) -> bool:
        redis = broker.redis
        if redis is None:
            return False
        key = PRESENCE_KEY.format(user_id=user_id)
        try:
            await redis.zremrangebyscore(key, "-inf", time.time() - PRESENCE_TTL_SECONDS)
            return (await redis.zcard(key)) > 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("Presence check failed: %s", type(exc).__name__)
            return False

    async def _presence_touch(self, user_id: str, socket_id: str) -> None:
        redis = broker.redis
        if redis is None:
            return
        key = PRESENCE_KEY.format(user_id=user_id)
        try:
            await redis.zadd(key, {socket_id: time.time()})
            await redis.expire(key, PRESENCE_TTL_SECONDS * 2)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Presence update failed: %s", type(exc).__name__)

    async def _presence_remove(self, user_id: str, socket_id: str, last_seen: Optional[str] = None) -> None:
        redis = broker.redis
        if redis is None:
            return
        try:
            await redis.zrem(PRESENCE_KEY.format(user_id=user_id), socket_id)
            if last_seen:
                await redis.set(LAST_SEEN_KEY.format(user_id=user_id), last_seen, ex=60 * 60 * 24 * 30)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Presence removal failed: %s", type(exc).__name__)

    async def _announce_offline_after_grace(self, user_id: str, last_seen: str) -> None:
        try:
            await asyncio.sleep(OFFLINE_GRACE_SECONDS)
        except asyncio.CancelledError:
            return
        self._offline_tasks.pop(user_id, None)
        if self.active_connections.get(user_id) or await self._is_online_shared(user_id):
            return  # still connected here or on another instance
        await self._announce(user_id, "offline", last_seen)

    async def _announce(self, user_id: str, state: str, at: str) -> None:
        try:
            contacts = await conversation_contacts(UUID(user_id))
        except Exception as exc:  # noqa: BLE001 - presence must never break a connection
            logger.warning("Could not load contacts for presence: %s", type(exc).__name__)
            return
        if contacts:
            await self.broadcast_to_users(
                "presence.changed", {"user_id": user_id, "status": state, "last_seen_at": at}, contacts
            )

    # ------------------------------------------------------------------ typing

    def handle_typing_start(self, conv_id: str, user_id: str, recipient_ids: List[UUID]) -> None:
        """Start or renew a typing indicator; it stops by itself after TYPING_TIMEOUT_SECONDS."""
        key = f"{conv_id}:{user_id}"
        existing = self.active_typing.pop(key, None)
        if existing:
            existing.cancel()
        else:
            # Only announce the start once per burst of keystrokes.
            self._spawn(self.broadcast_to_users(
                "typing.started", {"conversation_id": conv_id, "user_id": user_id}, recipient_ids
            ))

        async def _auto_stop():
            try:
                await asyncio.sleep(TYPING_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                return
            if self.active_typing.get(key) is task:
                del self.active_typing[key]
            await self.broadcast_to_users(
                "typing.stopped", {"conversation_id": conv_id, "user_id": user_id}, recipient_ids
            )

        task = self._spawn(_auto_stop())
        self.active_typing[key] = task

    def handle_typing_stop(self, conv_id: str, user_id: str, recipient_ids: List[UUID]) -> None:
        key = f"{conv_id}:{user_id}"
        existing = self.active_typing.pop(key, None)
        if existing is None:
            return  # nothing was announced
        existing.cancel()
        self._spawn(self.broadcast_to_users(
            "typing.stopped", {"conversation_id": conv_id, "user_id": user_id}, recipient_ids
        ))

    # ------------------------------------------------------------------ helpers

    def _spawn(self, coro) -> asyncio.Task:
        """Run a coroutine in the background, keeping a reference so it isn't garbage-collected."""
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task


manager = ConnectionManager()
