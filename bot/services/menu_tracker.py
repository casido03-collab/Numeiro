"""Redis-based tracking for clean Telegram UX.

Tracks per-user:
  - menu_msg_id  : last inline-menu message (replaced on every reply-button press)
  - kb_shown     : whether the persistent reply keyboard was sent (only send once)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MENU_TTL = 86_400       # 24 h
_KB_TTL   = 86_400 * 30  # 30 days


async def _r():
    from bot.services.cache import get_redis
    return await get_redis()


# ─── Menu message ─────────────────────────────────────────────────────────────

async def get_menu_msg_id(telegram_id: int) -> Optional[int]:
    try:
        v = await (await _r()).get(f"menu_msg:{telegram_id}")
        return int(v) if v else None
    except Exception as e:
        logger.debug("menu_tracker get: %s", e)
        return None


async def set_menu_msg_id(telegram_id: int, message_id: int) -> None:
    try:
        await (await _r()).set(f"menu_msg:{telegram_id}", message_id, ex=_MENU_TTL)
    except Exception as e:
        logger.debug("menu_tracker set: %s", e)


# ─── Reply keyboard ───────────────────────────────────────────────────────────

async def is_keyboard_shown(telegram_id: int) -> bool:
    try:
        return bool(await (await _r()).get(f"kb_shown:{telegram_id}"))
    except Exception:
        return False


async def mark_keyboard_shown(telegram_id: int) -> None:
    try:
        await (await _r()).set(f"kb_shown:{telegram_id}", "1", ex=_KB_TTL)
    except Exception:
        pass
