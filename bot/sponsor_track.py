"""Sponsor tracking via shared Redis (minerstars_redis @ 127.0.0.1:16379).

Usage in any bot's /start handler:
    from sponsor_track import track_sponsor_start
    await track_sponsor_start(message, "my_bot_username")

When a user starts the bot via deeplink t.me/bot?start=sponsor_USERID,
writes key sponsor:bot_username:user_id = 1 (TTL 30 days) to shared Redis.
The MinerStars bot reads these keys to verify bot-sponsor subscriptions.
"""
import logging
from redis.asyncio import Redis

_log = logging.getLogger("sponsor_track")
_REDIS_URL = "redis://minerstars_redis:6379/0"
_TTL = 30 * 86400  # 30 days


async def track_sponsor_start(message, bot_username: str) -> bool:
    """Call in /start handler. Returns True if this was a sponsor deeplink."""
    text = message.text or ""
    parts = text.split()
    if len(parts) < 2:
        return False
    arg = parts[1]
    if not arg.startswith("sponsor_"):
        return False
    try:
        sponsor_user_id = int(arg[8:])
    except ValueError:
        return False
    try:
        r = Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        key = f"sponsor:{bot_username}:{sponsor_user_id}"
        await r.set(key, "1", ex=_TTL)
        await r.aclose()
        _log.info("Sponsor tracked: %s", key)
    except Exception as e:
        _log.warning("sponsor_track redis write failed: %s", e)
    return True


async def track_self(message, bot_username: str) -> None:
    """Always mark that this user started this bot (for cross-promo verification)."""
    try:
        r = Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        uid = message.from_user.id
        key = f"sponsor:{bot_username}:{uid}"
        await r.set(key, "1", ex=_TTL)
        await r.aclose()
    except Exception:
        pass
