import json
import hashlib
import redis.asyncio as aioredis
from config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def make_cache_key(*parts) -> str:
    raw = ":".join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()


async def get_cached(key: str) -> str | None:
    r = await get_redis()
    return await r.get(f"numeiro:{key}")


async def set_cached(key: str, value: str, ttl: int = 3600 * 24 * 7) -> None:
    r = await get_redis()
    await r.setex(f"numeiro:{key}", ttl, value)


async def get_cached_json(key: str) -> dict | None:
    raw = await get_cached(key)
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            return None
    return None


async def set_cached_json(key: str, value: dict, ttl: int = 3600 * 24 * 7) -> None:
    await set_cached(key, json.dumps(value, ensure_ascii=False), ttl)


async def rate_limit_check(user_id: int, action: str, max_count: int, window_seconds: int) -> bool:
    """Return True if within limit, False if exceeded."""
    r = await get_redis()
    key = f"rl:{action}:{user_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, window_seconds)
    return count <= max_count


async def get_cooldown_remaining(user_id: int, action: str) -> int:
    """Return remaining seconds of cooldown, 0 if no cooldown."""
    r = await get_redis()
    key = f"rl:{action}:{user_id}"
    ttl = await r.ttl(key)
    return max(0, ttl)


async def set_user_processing(user_id: int) -> bool:
    """Mark user as currently processing request. Returns False if already processing."""
    r = await get_redis()
    key = f"processing:{user_id}"
    result = await r.set(key, "1", ex=60, nx=True)
    return result is not None


async def clear_user_processing(user_id: int) -> None:
    r = await get_redis()
    await r.delete(f"processing:{user_id}")
