"""Redis-сессии для VK-диалога. Изолированы от Telegram (префикс vk:)."""
import json
import logging
import time

from bot.services.cache import get_redis

logger = logging.getLogger(__name__)

_TTL = 86_400 * 7  # 7 дней


# ─── Internal ─────────────────────────────────────────────────────────────────

async def _get(uid: int) -> dict:
    try:
        r = await get_redis()
        val = await r.get(f"vk:{uid}")
        return json.loads(val) if val else {}
    except Exception as e:
        logger.warning("vk session get error: %s", e)
        return {}


async def _set(uid: int, data: dict) -> None:
    try:
        r = await get_redis()
        await r.set(f"vk:{uid}", json.dumps(data, ensure_ascii=False), ex=_TTL)
    except Exception as e:
        logger.warning("vk session set error: %s", e)


# ─── Stage ────────────────────────────────────────────────────────────────────

async def get_stage(uid: int) -> str:
    return (await _get(uid)).get("stage", "new")


async def set_stage(uid: int, stage: str) -> None:
    sess = await _get(uid)
    sess["stage"] = stage
    await _set(uid, sess)


# ─── Profile ──────────────────────────────────────────────────────────────────

async def get_profile(uid: int) -> dict:
    return (await _get(uid)).get("profile", {})


async def store_field(uid: int, key: str, value) -> None:
    sess = await _get(uid)
    profile = sess.get("profile", {})
    profile[key] = value
    sess["profile"] = profile
    await _set(uid, sess)


# ─── Free dialog ──────────────────────────────────────────────────────────────

async def get_free_count(uid: int) -> int:
    return (await _get(uid)).get("free_count", 0)


async def increment_free_count(uid: int) -> None:
    sess = await _get(uid)
    sess["free_count"] = sess.get("free_count", 0) + 1
    await _set(uid, sess)


# ─── Follow-up ────────────────────────────────────────────────────────────────

async def get_followup_left(uid: int) -> int:
    return (await _get(uid)).get("followup_left", 0)


async def set_followup_left(uid: int, n: int) -> None:
    sess = await _get(uid)
    sess["followup_left"] = n
    await _set(uid, sess)


async def decrement_followup(uid: int) -> int:
    sess = await _get(uid)
    left = max(0, sess.get("followup_left", 0) - 1)
    sess["followup_left"] = left
    await _set(uid, sess)
    return left


# ─── Paid tier ────────────────────────────────────────────────────────────────

async def get_paid_tier(uid: int) -> str | None:
    return (await _get(uid)).get("paid_tier")


async def set_paid_tier(uid: int, tier_key: str) -> None:
    sess = await _get(uid)
    sess["paid_tier"] = tier_key
    await _set(uid, sess)


# ─── Tier message counter (accompaniment) ─────────────────────────────────────

async def get_tier_msg_count(uid: int) -> int:
    return (await _get(uid)).get("tier_msg_count", 0)


async def increment_tier_msg_count(uid: int) -> None:
    sess = await _get(uid)
    sess["tier_msg_count"] = sess.get("tier_msg_count", 0) + 1
    await _set(uid, sess)


# ─── History (последние 10 сообщений) ─────────────────────────────────────────

async def append_history(uid: int, role: str, text: str) -> None:
    sess = await _get(uid)
    history = sess.get("history", [])
    history.append({"role": role, "text": text[:500]})
    if len(history) > 10:
        history = history[-10:]
    sess["history"] = history
    await _set(uid, sess)


async def get_history(uid: int) -> list:
    return (await _get(uid)).get("history", [])


def format_history(history: list) -> str:
    lines = []
    for h in history:
        role = "Клиент" if h["role"] == "user" else "Аиша"
        lines.append(f"{role}: {h['text']}")
    return "\n".join(lines)


# ─── Payment ──────────────────────────────────────────────────────────────────

async def set_payment_offered(uid: int) -> None:
    r = await get_redis()
    await r.set(f"vk:pay_offered:{uid}", str(int(time.time())), ex=86400 * 7)


async def get_payment_offered_at(uid: int) -> int | None:
    r = await get_redis()
    val = await r.get(f"vk:pay_offered:{uid}")
    return int(val) if val else None


# ─── Activity ─────────────────────────────────────────────────────────────────

async def set_last_activity(uid: int) -> None:
    r = await get_redis()
    await r.set(f"vk:activity:{uid}", str(int(time.time())), ex=86400 * 30)


async def get_last_activity(uid: int) -> int | None:
    r = await get_redis()
    val = await r.get(f"vk:activity:{uid}")
    return int(val) if val else None


# ─── Next tier (upsell) ───────────────────────────────────────────────────────

async def reset_session(uid: int) -> None:
    r = await get_redis()
    await r.delete(f"vk:{uid}")


# ─── Реестр пользователей (для планировщика пушей) ───────────────────────────

async def register_user(uid: int) -> None:
    """Добавить uid в глобальный реестр VK-пользователей."""
    try:
        r = await get_redis()
        await r.sadd("vk:users", uid)
    except Exception as e:
        logger.warning("vk register_user error: %s", e)


async def get_all_user_ids() -> list[int]:
    """Вернуть список всех VK user ID из реестра."""
    try:
        r = await get_redis()
        members = await r.smembers("vk:users")
        return [int(m) for m in members]
    except Exception as e:
        logger.warning("vk get_all_user_ids error: %s", e)
        return []


async def get_vk_reminder_sent(uid: int) -> bool:
    r = await get_redis()
    return bool(await r.get(f"vk:reminder_sent:{uid}"))


async def set_vk_reminder_sent(uid: int) -> None:
    r = await get_redis()
    await r.set(f"vk:reminder_sent:{uid}", "1", ex=86400 * 7)
