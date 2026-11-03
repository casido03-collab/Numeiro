"""Serialize legacy dialogue payment delivery and acknowledge only completed work."""
from contextlib import asynccontextmanager
from uuid import uuid4
from bot.services.cache import get_redis


@asynccontextmanager
async def payment_guard(namespace, payment_id):
    r = await get_redis()
    done, lock = f"{namespace}:{payment_id}", f"{namespace}:lock:{payment_id}"
    if await r.exists(done):
        yield False
        return
    token = uuid4().hex
    if not await r.set(lock, token, nx=True, ex=300):
        raise RuntimeError("Payment delivery is already in progress; retry later")
    try:
        if await r.exists(done):
            yield False
        else:
            yield True
            await r.set(done, "1")
    finally:
        await r.eval("if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0", 1, lock, token)


async def extend_dialogue_subscription(platform, user_id, payment_id, days=30):
    from time import time
    r = await get_redis()
    return await r.eval("""
        if redis.call('EXISTS', KEYS[2]) == 1 then return redis.call('GET', KEYS[1]) end
        local expires = math.max(tonumber(ARGV[1]), tonumber(redis.call('GET', KEYS[1]) or '0')) + tonumber(ARGV[2])
        redis.call('SET', KEYS[1], expires, 'EX', expires - tonumber(ARGV[1]) + 86400)
        redis.call('SET', KEYS[2], '1')
        return expires
    """, 2, f"{platform}:paid_until:{user_id}", f"{platform}:subscription_grant:{payment_id}", int(time()), days * 86400)
