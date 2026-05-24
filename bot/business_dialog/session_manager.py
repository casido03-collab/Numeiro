"""Redis-based session state для business dialog.

Ключ: biz:{telegram_id}
Структура JSON:
{
  "stage": "new|collecting_name|...|completed",
  "free_count": 3,
  "last_deflect": 7,
  "biz_conn_id": "...",
  "profile": {
    "name": "...", "birth_date": "...", "city": "...",
    "problem": "...", "intent": "...", "product_name": "..."
  },
  "followup_left": 2
}
"""
import json
import logging
from bot.services.cache import get_redis

logger = logging.getLogger(__name__)

_TTL = 86_400 * 7   # 7 дней — хватит на весь цикл консультации
FOLLOWUP_LIMIT = 2


# ─── Базовые операции ─────────────────────────────────────────────────────────

async def _get(telegram_id: int) -> dict:
    try:
        r = await get_redis()
        val = await r.get(f"biz:{telegram_id}")
        return json.loads(val) if val else {}
    except Exception as e:
        logger.warning("biz session get error: %s", e)
        return {}


async def _set(telegram_id: int, data: dict) -> None:
    try:
        r = await get_redis()
        await r.set(f"biz:{telegram_id}", json.dumps(data, ensure_ascii=False), ex=_TTL)
    except Exception as e:
        logger.warning("biz session set error: %s", e)


# ─── Stage ────────────────────────────────────────────────────────────────────

async def get_biz_stage(telegram_id: int) -> str:
    sess = await _get(telegram_id)
    return sess.get("stage", "new")


async def set_biz_stage(telegram_id: int, stage: str) -> None:
    sess = await _get(telegram_id)
    sess["stage"] = stage
    await _set(telegram_id, sess)


# ─── Business connection id ───────────────────────────────────────────────────

async def store_biz_conn(telegram_id: int, biz_conn_id: str) -> None:
    sess = await _get(telegram_id)
    sess["biz_conn_id"] = biz_conn_id
    await _set(telegram_id, sess)


async def get_biz_conn(telegram_id: int) -> str | None:
    sess = await _get(telegram_id)
    return sess.get("biz_conn_id") or None


# ─── Profile ──────────────────────────────────────────────────────────────────

async def store_profile_field(telegram_id: int, field: str, value: str) -> None:
    sess = await _get(telegram_id)
    profile = sess.get("profile", {})
    profile[field] = value
    sess["profile"] = profile
    await _set(telegram_id, sess)


async def get_profile(telegram_id: int) -> dict:
    sess = await _get(telegram_id)
    return sess.get("profile", {})


# ─── Free message counter ─────────────────────────────────────────────────────

async def get_free_count(telegram_id: int) -> int:
    sess = await _get(telegram_id)
    return sess.get("free_count", 0)


async def increment_free_count(telegram_id: int) -> int:
    sess = await _get(telegram_id)
    count = sess.get("free_count", 0) + 1
    sess["free_count"] = count
    await _set(telegram_id, sess)
    return count


async def is_free_limit_reached(telegram_id: int) -> bool:
    from bot.business_dialog.anti_free_chat import FREE_MSG_LIMIT
    return await get_free_count(telegram_id) >= FREE_MSG_LIMIT


# ─── Deflect rotation ─────────────────────────────────────────────────────────

async def get_last_deflect(telegram_id: int) -> int:
    sess = await _get(telegram_id)
    return sess.get("last_deflect", -1)


async def set_last_deflect(telegram_id: int, idx: int) -> None:
    sess = await _get(telegram_id)
    sess["last_deflect"] = idx
    await _set(telegram_id, sess)


# ─── Follow-up counter ────────────────────────────────────────────────────────

async def get_followup_left(telegram_id: int) -> int:
    sess = await _get(telegram_id)
    return sess.get("followup_left", FOLLOWUP_LIMIT)


async def decrement_followup(telegram_id: int) -> int:
    sess = await _get(telegram_id)
    left = max(0, sess.get("followup_left", FOLLOWUP_LIMIT) - 1)
    sess["followup_left"] = left
    await _set(telegram_id, sess)
    return left


async def set_followup_left(telegram_id: int, n: int) -> None:
    sess = await _get(telegram_id)
    sess["followup_left"] = n
    await _set(telegram_id, sess)


# ─── Payment offered timestamp ────────────────────────────────────────────────

async def set_payment_offered(telegram_id: int) -> None:
    """Зафиксировать момент когда была показана ссылка на оплату (однократно)."""
    import time
    sess = await _get(telegram_id)
    if "payment_offered_at" not in sess:
        sess["payment_offered_at"] = int(time.time())
        await _set(telegram_id, sess)


async def get_payment_offered_at(telegram_id: int) -> int | None:
    """Вернуть unix-timestamp когда была показана ссылка на оплату."""
    sess = await _get(telegram_id)
    return sess.get("payment_offered_at")


# ─── Reset ────────────────────────────────────────────────────────────────────

async def reset_session(telegram_id: int) -> None:
    try:
        r = await get_redis()
        await r.delete(f"biz:{telegram_id}")
    except Exception as e:
        logger.warning("biz session reset error: %s", e)
