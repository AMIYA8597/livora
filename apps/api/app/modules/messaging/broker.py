"""
Distributed Event Broker for Real-Time Communication.
Supports Redis Pub/Sub for multi-instance deployments with seamless fallback
to in-memory event dispatch when Redis is not available.
"""
import asyncio
import json
import logging
from typing import List, Optional, Set, Any
from uuid import UUID
from datetime import datetime, timezone

import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL_CHAT_EVENTS = "flatmate:chat:events"

class DistributedEventBroker:
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._is_redis_connected: bool = False
        self._local_listeners: Set[Any] = set()

    async def initialize(self) -> None:
        """Initialize Redis connection if available; fallback gracefully if unreachable."""
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379")
        try:
            client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            await asyncio.wait_for(client.ping(), timeout=1.5)
            self._redis_client = client
            self._is_redis_connected = True
            logger.info("DistributedEventBroker: Connected to Redis Pub/Sub at %s", redis_url)
            # Start pubsub background listener
            self._pubsub_task = asyncio.create_task(self._listen_redis())
        except Exception as e:
            logger.warning("DistributedEventBroker: Redis unavailable (%s). Running in standalone local mode.", e)
            self._redis_client = None
            self._is_redis_connected = False

    async def shutdown(self) -> None:
        """Graceful shutdown of Redis client and listener."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
        self._is_redis_connected = False

    def register_local_listener(self, listener) -> None:
        """Register the local ConnectionManager to receive events from the broker."""
        self._local_listeners.add(listener)

    def unregister_local_listener(self, listener) -> None:
        self._local_listeners.discard(listener)

    async def publish(self, event_type: str, data: dict, target_user_ids: Optional[List[UUID]] = None, correlation_id: Optional[str] = None) -> None:
        """
        Publish an event to all nodes via Redis, or to local connections if standalone.
        """
        envelope = {
            "version": "1.0",
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "target_user_ids": [str(u) for u in target_user_ids] if target_user_ids is not None else None,
            "data": data,
        }
        payload_str = json.dumps(envelope)

        # 1. Distribute via Redis Pub/Sub if connected
        if self._is_redis_connected and self._redis_client:
            try:
                await self._redis_client.publish(CHANNEL_CHAT_EVENTS, payload_str)
                return
            except Exception as e:
                logger.warning("Failed to publish to Redis (%s), falling back to local dispatch", e)

        # 2. Local fallback dispatch
        await self._dispatch_local(envelope)

    async def _listen_redis(self) -> None:
        """Background loop subscribing to Redis pub/sub."""
        if not self._redis_client:
            return
        try:
            pubsub = self._redis_client.pubsub()
            await pubsub.subscribe(CHANNEL_CHAT_EVENTS)
            logger.info("Subscribed to Redis channel: %s", CHANNEL_CHAT_EVENTS)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        envelope = json.loads(message["data"])
                        await self._dispatch_local(envelope)
                    except Exception as err:
                        logger.error("Error decoding Redis event message: %s", err)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis listener exception: %s. Swapping to local mode.", e)
            self._is_redis_connected = False

    async def _dispatch_local(self, envelope: dict) -> None:
        """Deliver envelope to local ConnectionManager listeners."""
        for listener in list(self._local_listeners):
            try:
                await listener.on_broker_event(envelope)
            except Exception as e:
                logger.error("Error dispatching to local listener: %s", e)

broker = DistributedEventBroker()
