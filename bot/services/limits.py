"""Управление лимитами пользователей.

Логика периодов:
- FREE:  лимиты НЕ сбрасываются — даются ОДИН РАЗ навсегда (period_start = "free_total")
         Исключение: daily_forecasts — 1 в день как у всех.
- PAID:  лимиты на весь период подписки (period_start = дата активации)
  Исключение: daily_forecasts — "1 в день" для всех тарифов, сбрасывается ежедневно.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import UsageLimits, Subscription, PlanEnum, SubscriptionStatusEnum
from config import PLANS


# Лимиты которые сбрасываются каждый день даже для платных тарифов
_DAILY_RESET_LIMITS = frozenset({"daily_forecasts"})


async def get_user_plan(session: AsyncSession, user_id: int) -> str:
    """Get current active plan for user."""
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return "free"
    if sub.status != SubscriptionStatusEnum.active:
        return "free"
    if sub.expires_at and sub.expires_at < datetime.now(timezone.utc):
        sub.status = SubscriptionStatusEnum.expired
        await session.commit()
        return "free"
    return sub.plan.value


async def _period_key_for_paid(session: AsyncSession, user_id: int, plan: str) -> str:
    """Вычислить ключ периода для платного пользователя.
    Ключ = дата активации подписки (expires_at - days из плана).
    """
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub and sub.expires_at:
        plan_days = PLANS.get(plan, {}).get("days", 30)
        activation_dt = sub.expires_at - timedelta(days=plan_days)
        return activation_dt.strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _get_or_create_record(
    session: AsyncSession, user_id: int, period_key: str
) -> UsageLimits:
    """Получить или создать запись UsageLimits для заданного period_key."""
    result = await session.execute(
        select(UsageLimits).where(
            UsageLimits.user_id == user_id,
            UsageLimits.period_start == period_key,
        )
    )
    usage = result.scalar_one_or_none()
    if not usage:
        usage = UsageLimits(user_id=user_id, period_start=period_key)
        session.add(usage)
        await session.commit()
        await session.refresh(usage)
    return usage


async def get_or_create_usage(session: AsyncSession, user_id: int) -> UsageLimits:
    """Получить запись использования для пользователя.
    Для FREE: сегодняшняя запись (ежедневный сброс).
    Для PAID: запись на период подписки.
    Используется в _activate_subscription и других местах.
    """
    plan = await get_user_plan(session, user_id)
    if plan == "free":
        return await _get_or_create_record(session, user_id, "free_total")
    period_key = await _period_key_for_paid(session, user_id, plan)
    return await _get_or_create_record(session, user_id, period_key)


async def _get_usage_for_limit(
    session: AsyncSession, user_id: int, plan: str, limit_type: str
) -> UsageLimits:
    """Выбрать правильную запись в зависимости от типа лимита и тарифа.
    - daily_forecasts: всегда ежедневная запись
    - остальные: ежедневная для free, периодическая для paid
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if limit_type in _DAILY_RESET_LIMITS:
        return await _get_or_create_record(session, user_id, today)
    if plan == "free":
        return await _get_or_create_record(session, user_id, "free_total")
    period_key = await _period_key_for_paid(session, user_id, plan)
    return await _get_or_create_record(session, user_id, period_key)


LIMIT_FIELD_MAP = {
    "ai_messages":        "ai_messages",
    "personal_questions": "personal_questions",
    "weekly_reports":     "weekly_reports",
    "compatibility":      "compatibility",
    "daily_forecasts":    "daily_forecasts",
    "mini_readings":      "mini_readings",
    "date_selections":    "date_selections",
    "tarot_cards":        "tarot_cards",
    "matrix_readings":    "matrix_readings",
}


async def check_limit(
    session: AsyncSession, user_id: int, limit_type: str
) -> tuple[bool, int, int]:
    """
    Проверить доступность лимита.
    Returns (has_limit, used, max_allowed).
    """
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    max_allowed = plan_limits.get(limit_type, 0)

    if max_allowed == 0:
        return False, 0, 0

    usage = await _get_usage_for_limit(session, user_id, plan, limit_type)
    field = LIMIT_FIELD_MAP.get(limit_type, "ai_messages")
    used = getattr(usage, field, 0)

    return used < max_allowed, used, max_allowed


async def consume_limit(
    session: AsyncSession, user_id: int, limit_type: str
) -> bool:
    """Потратить единицу лимита. Returns True если успешно."""
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    max_allowed = plan_limits.get(limit_type, 0)

    if max_allowed == 0:
        return False

    usage = await _get_usage_for_limit(session, user_id, plan, limit_type)
    field = LIMIT_FIELD_MAP.get(limit_type, "ai_messages")
    used = getattr(usage, field, 0)

    if used >= max_allowed:
        return False

    setattr(usage, field, used + 1)
    await session.commit()

    # Ежедневный Redis-трекинг для статистики
    if limit_type == "ai_messages":
        try:
            from bot.services.cache import get_redis
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            r = await get_redis()
            await r.incr(f"stats:ai:count:{today}")
            await r.expire(f"stats:ai:count:{today}", 86400 * 7)
            await r.sadd(f"stats:ai:users:{today}", user_id)
            await r.expire(f"stats:ai:users:{today}", 86400 * 7)
        except Exception:
            pass  # статистика не критична

    return True


async def get_limits_summary(session: AsyncSession, user_id: int) -> dict:
    """Получить сводку лимитов для отображения в кабинете."""
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if plan == "free":
        period_key = "free_total"
    else:
        period_key = await _period_key_for_paid(session, user_id, plan)

    period_usage = await _get_or_create_record(session, user_id, period_key)

    # Для daily_forecasts нужна сегодняшняя запись (может совпадать с period_usage у free)
    if period_key == today:
        daily_usage = period_usage
    else:
        daily_usage = await _get_or_create_record(session, user_id, today)

    summary = {}
    for limit_type, field in LIMIT_FIELD_MAP.items():
        max_val = plan_limits.get(limit_type, 0)
        usage = daily_usage if limit_type in _DAILY_RESET_LIMITS else period_usage
        used = getattr(usage, field, 0)
        summary[limit_type] = {
            "used": used,
            "max": max_val,
            "remaining": max(0, max_val - used),
        }
    return summary


async def is_vip(user_id: int) -> bool:
    from bot.services.cache import get_redis
    return bool(await (await get_redis()).exists(f"vip:{user_id}"))


async def activate_vip(user_id: int, days: int = 30, event_id: str | None = None) -> None:
    """Extend remaining time and add quotas, atomically; retries do not grant twice."""
    from bot.services.cache import get_redis
    from config import VIP_PLAN
    r = await get_redis()
    keys = [f"vip:{user_id}", f"grant:{event_id}" if event_id else f"unused:{user_id}"]
    keys += [f"vip_limit:{product}:{user_id}" for product in VIP_PLAN["limits"]]
    await r.eval("""
        if ARGV[1] == '1' and redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
        local remaining = math.max(0, redis.call('TTL', KEYS[1]))
        local ttl = remaining + tonumber(ARGV[2])
        redis.call('SET', KEYS[1], '1', 'EX', ttl)
        for i=3,#KEYS do
            local old = 0
            if remaining > 0 then old = tonumber(redis.call('GET', KEYS[i]) or '0') end
            redis.call('SET', KEYS[i], old + tonumber(ARGV[i]), 'EX', ttl)
        end
        if ARGV[1] == '1' then redis.call('SET', KEYS[2], '1') end
        return ttl
    """, len(keys), *keys, "1" if event_id else "0", days * 86400, *VIP_PLAN["limits"].values())


async def check_vip_limit(user_id: int, product_key: str) -> bool:
    from bot.services.cache import get_redis
    r = await get_redis()
    return bool(await is_vip(user_id) and int(await r.get(f"vip_limit:{product_key}:{user_id}") or 0) > 0)


async def has_credit(user_id: int, product_key: str) -> bool:
    from bot.services.cache import get_redis
    r = await get_redis()
    return int(await r.get(f"oneoff:{product_key}:{user_id}") or 0) > 0


async def can_use_product(user_id: int, product_key: str) -> bool:
    return await check_vip_limit(user_id, product_key) or await has_credit(user_id, product_key)


async def consume_product(user_id: int, product_key: str, result_id: str) -> bool:
    """One debit per durable result, even after retries or a DB commit failure."""
    from bot.services.cache import get_redis
    r = await get_redis()
    return bool(await r.eval("""
        if redis.call('EXISTS', KEYS[1]) == 1 then return 1 end
        local source = KEYS[4]
        if redis.call('EXISTS', KEYS[2]) == 1 and tonumber(redis.call('GET', KEYS[3]) or '0') > 0 then
            source = KEYS[3]
        end
        if tonumber(redis.call('GET', source) or '0') <= 0 then return 0 end
        redis.call('DECR', source)
        redis.call('SET', KEYS[1], source)
        return 1
    """, 4, f"spent:{result_id}", f"vip:{user_id}",
        f"vip_limit:{product_key}:{user_id}", f"oneoff:{product_key}:{user_id}"))


async def _decrement(key: str) -> bool:
    from bot.services.cache import get_redis
    r = await get_redis()
    return bool(await r.eval("""
        if tonumber(redis.call('GET', KEYS[1]) or '0') <= 0 then return 0 end
        redis.call('DECR', KEYS[1])
        return 1
    """, 1, key))


async def use_vip_limit(user_id: int, product_key: str) -> bool:
    return await is_vip(user_id) and await _decrement(f"vip_limit:{product_key}:{user_id}")


async def use_credit(user_id: int, product_key: str) -> bool:
    return await _decrement(f"oneoff:{product_key}:{user_id}")


async def add_credit(user_id: int, product_key: str, amount: int = 1, event_id: str | None = None) -> None:
    from bot.services.cache import get_redis
    r = await get_redis()
    await r.eval("""
        if ARGV[1] == '1' and redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
        redis.call('INCRBY', KEYS[1], ARGV[2])
        redis.call('PERSIST', KEYS[1])
        if ARGV[1] == '1' then redis.call('SET', KEYS[2], '1') end
        return 1
    """, 2, f"oneoff:{product_key}:{user_id}", f"grant:{event_id}",
        "1" if event_id else "0", amount)


async def get_vip_limits_summary(user_id: int) -> dict:
    from bot.services.cache import get_redis
    from config import VIP_PLAN
    r = await get_redis()
    active = await is_vip(user_id)
    result = {}
    for product, quota in VIP_PLAN["limits"].items():
        remaining = int(await r.get(f"vip_limit:{product}:{user_id}") or 0) if active else 0
        result[product] = {"remaining": remaining, "max": max(quota, remaining)}
    return result
