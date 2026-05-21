"""Управление лимитами пользователей."""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import UsageLimits, Subscription, PlanEnum, SubscriptionStatusEnum
from config import PLANS


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


async def get_or_create_usage(session: AsyncSession, user_id: int) -> UsageLimits:
    """Get or create today's usage record for user."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await session.execute(
        select(UsageLimits).where(
            UsageLimits.user_id == user_id,
            UsageLimits.period_start == today,
        )
    )
    usage = result.scalar_one_or_none()
    if not usage:
        usage = UsageLimits(user_id=user_id, period_start=today)
        session.add(usage)
        await session.commit()
        await session.refresh(usage)
    return usage


LIMIT_FIELD_MAP = {
    "ai_messages": "ai_messages",
    "personal_questions": "personal_questions",
    "weekly_reports": "weekly_reports",
    "compatibility": "compatibility",
    "daily_forecasts": "daily_forecasts",
    "mini_readings": "mini_readings",
    "date_selections": "date_selections",
}


async def check_limit(session: AsyncSession, user_id: int, limit_type: str) -> tuple[bool, int, int]:
    """
    Check if user has available limit.
    Returns (has_limit, used, max_allowed).
    """
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    max_allowed = plan_limits.get(limit_type, 0)

    if max_allowed == 0:
        return False, 0, 0

    usage = await get_or_create_usage(session, user_id)
    field = LIMIT_FIELD_MAP.get(limit_type, "ai_messages")
    used = getattr(usage, field, 0)

    return used < max_allowed, used, max_allowed


async def consume_limit(session: AsyncSession, user_id: int, limit_type: str) -> bool:
    """Consume one unit of limit. Returns True if successful."""
    has_limit, used, max_allowed = await check_limit(session, user_id, limit_type)
    if not has_limit:
        return False

    usage = await get_or_create_usage(session, user_id)
    field = LIMIT_FIELD_MAP.get(limit_type, "ai_messages")
    setattr(usage, field, getattr(usage, field, 0) + 1)
    await session.commit()
    return True


async def get_limits_summary(session: AsyncSession, user_id: int) -> dict:
    """Get full limits summary for user."""
    plan = await get_user_plan(session, user_id)
    plan_limits = PLANS[plan]["limits"]
    usage = await get_or_create_usage(session, user_id)

    summary = {}
    for limit_type, field in LIMIT_FIELD_MAP.items():
        max_val = plan_limits.get(limit_type, 0)
        used = getattr(usage, field, 0)
        summary[limit_type] = {
            "used": used,
            "max": max_val,
            "remaining": max(0, max_val - used),
        }
    return summary
