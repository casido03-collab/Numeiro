"""Push-уведомления и задачи по расписанию."""
import random
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

PUSH_MESSAGES_ACTIVE = [
    "✨ {name}, сегодня энергия дня может подсказать тебе важное решение. Открыть прогноз?",
    "🌙 {name}, на этой неделе у тебя усиливается интуиция. Заглянем в прогноз?",
    "🔮 Судьба приготовила для тебя новые знаки. Открыть прогноз?",
    "✨ {name}, твой персональный расклад уже готов...",
    "🌌 Возможно, сегодня хороший день, чтобы задать важный вопрос...",
]

PUSH_MESSAGES_INACTIVE = [
    "🌙 {name}, прошло несколько дней. Числа твоей судьбы не дремлют...",
    "✨ Всегда рады видеть тебя снова, {name}. Что тебя ждёт на этой неделе?",
    "🔮 {name}, твои энергии за это время изменились. Хочешь посмотреть?",
]

REMINDER_MESSAGES = [
    "⏰ {name}, твоя подписка истекает завтра. Продлить доступ к прогнозам?",
    "✨ {name}, ещё 24 часа до окончания подписки. Не прерывай поток знаний!",
]


async def send_daily_pushes(bot: Bot, session: AsyncSession):
    """Send daily forecast push to subscribed users."""
    from bot.models.user import User, Subscription, SubscriptionStatusEnum, PlanEnum
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    now = datetime.now(timezone.utc)
    # Отправляем только между 9:00 и 20:00 по МСК (UTC+3)
    msk_hour = (now.hour + 3) % 24
    if msk_hour < 9 or msk_hour >= 20:
        return

    result = await session.execute(
        select(User).join(Subscription).where(
            Subscription.status == SubscriptionStatusEnum.active,
            Subscription.plan != PlanEnum.free,
        )
    )
    users = result.scalars().all()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Открыть энергию дня", callback_data="menu:daily")],
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data="weekly:start")],
        [InlineKeyboardButton(text="📜 Тарифы", callback_data="menu:plans")],
    ])

    for user in users:
        name = user.first_name or "друг"
        text = random.choice(PUSH_MESSAGES_ACTIVE).format(name=name)
        try:
            await bot.send_message(user.telegram_id, text, reply_markup=kb)
        except Exception:
            pass


async def send_subscription_reminders(bot: Bot, session: AsyncSession):
    """Remind users 24h before subscription expires."""
    from bot.models.user import User, Subscription, SubscriptionStatusEnum, PlanEnum
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    tomorrow = datetime.now(timezone.utc) + timedelta(hours=24)
    window_start = datetime.now(timezone.utc) + timedelta(hours=23)

    result = await session.execute(
        select(User).join(Subscription).where(
            Subscription.status == SubscriptionStatusEnum.active,
            Subscription.plan != PlanEnum.free,
            Subscription.expires_at >= window_start,
            Subscription.expires_at <= tomorrow,
        )
    )
    users = result.scalars().all()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="menu:plans")],
        [InlineKeyboardButton(text="📜 Открыть тарифы", callback_data="menu:plans")],
    ])

    for user in users:
        name = user.first_name or "друг"
        text = random.choice(REMINDER_MESSAGES).format(name=name)
        try:
            await bot.send_message(user.telegram_id, text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass


def setup_scheduler(bot: Bot, session_maker) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def _daily_push():
        async with session_maker() as session:
            await send_daily_pushes(bot, session)

    async def _reminders():
        async with session_maker() as session:
            await send_subscription_reminders(bot, session)

    async def _retention():
        from bot.services.retention import run_retention_pushes
        async with session_maker() as session:
            await run_retention_pushes(bot, session)

    async def _trial_upsell():
        from bot.services.retention import run_trial_upsell
        async with session_maker() as session:
            await run_trial_upsell(bot, session)

    # Ежедневные пуши в 9:00 МСК
    scheduler.add_job(_daily_push, CronTrigger(hour=6, minute=0))
    # Напоминания об окончании подписки в 12:00 МСК
    scheduler.add_job(_reminders, CronTrigger(hour=9, minute=0))
    # Retention push — каждые 10 минут (проверяет 24ч неактивности)
    scheduler.add_job(_retention, CronTrigger(minute="*/10"))
    # Trial upsell — каждые 5 минут (проверяет 1ч неактивности для free)
    scheduler.add_job(_trial_upsell, CronTrigger(minute="*/5"))

    return scheduler
