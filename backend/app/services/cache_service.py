import json
from typing import Any, Optional
import redis.asyncio as redis
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> Optional[redis.Redis]:
    """Provides a singleton async Redis connection."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            return None
    return _redis_client


async def check_redis_health() -> bool:
    """Pings Redis to verify service health."""
    try:
        client = await get_redis_client()
        if client:
            await client.ping()
            return True
        return False
    except Exception as e:
        logger.debug(f"Redis ping failed: {e}")
        return False


class CacheService:
    """Async cache service with graceful fallback on Redis unavailability."""

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        try:
            client = await get_redis_client()
            if client:
                val = await client.get(key)
                if val:
                    return json.loads(val)
        except Exception as e:
            logger.debug(f"Redis get failed for key {key}: {e}")
        return None

    @staticmethod
    async def set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
        try:
            client = await get_redis_client()
            if client:
                await client.set(key, json.dumps(value), ex=ttl_seconds)
                return True
        except Exception as e:
            logger.debug(f"Redis set failed for key {key}: {e}")
        return False
