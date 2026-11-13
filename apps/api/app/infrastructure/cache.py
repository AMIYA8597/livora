import json
from typing import Optional, Any
import redis.asyncio as aioredis
from app.core.config import settings

redis_client: Optional[aioredis.Redis] = None

async def init_redis() -> None:
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        print("Connected to Redis successfully.")
    except Exception as e:
        print(f"Warning: Redis connection failed ({e}). Cache running in bypass mode.")
        redis_client = None

async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.close()

async def get_cache(key: str) -> Optional[Any]:
    if not redis_client:
        return None
    try:
        data = await redis_client.get(key)
        return json.loads(data) if data else None
    except Exception:
        return None

async def set_cache(key: str, value: Any, ttl_seconds: int = 300) -> None:
    if not redis_client:
        return
    try:
        await redis_client.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        pass

async def delete_cache(key: str) -> None:
    if not redis_client:
        return
    try:
        await redis_client.delete(key)
    except Exception:
        pass
