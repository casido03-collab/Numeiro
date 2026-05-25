"""Управление лимитами пользователей.

Логика периодов:
- FREE:  лимиты сбрасываются ежедневно (period_start = сегодня)
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if plan == "free":
        return await _get_or_create_record(session, user_id, today)
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
    if plan == "free" or limit_type in _DAILY_RESET_LIMITS:
        return await _get_or_create_record(session, user_id, today)
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
    return True


async def get_limits_summary(session: AsyncSession, user_id: int) -> dict:
    """Получить сводку лимитов для отображения в кабинете."""
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if plan == "free":
        period_key = today
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
