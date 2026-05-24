"""Push-уведомления и задачи по расписанию."""
import random
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot

PUSH_MESSAGES_ACTIVE = [
    "✨ {name}, сегодня энергия дня может подсказать вам важное решение. Открыть прогноз?",
    "🌙 {name}, на этой неделе у вас усиливается интуиция. Заглянем в прогноз?",
    "🔮 Судьба приготовила для вас новые знаки. Открыть прогноз?",
    "✨ {name}, ваш персональный расклад уже готов...",
    "🌌 Возможно, сегодня хороший день, чтобы задать важный вопрос...",
]

PUSH_MESSAGES_INACTIVE = [
    "🌙 {name}, прошло несколько дней. Числа вашей судьбы не дремлют...",
    "✨ Всегда рады видеть вас снова, {name}. Что вас ждёт на этой неделе?",
    "🔮 {name}, ваши энергии за это время изменились. Хотите посмотреть?",
]

REMINDER_MESSAGES = [
    "⏰ {name}, ваша подписка истекает завтра. Продлить доступ к прогнозам?",
    "✨ {name}, ещё 24 часа до окончания подписки. Не прерывайте поток знаний!",
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

    PUSH_BUTTONS = [
        ("⚡ Энергия дня", "menu:daily"),
        ("✨ Мой разбор", "menu:reading"),
        ("🌟 Полная матрица судьбы", "matrix:start"),
        ("📅 Прогноз на неделю", "weekly:start"),
        ("💞 Совместимость", "menu:compatibility"),
        ("🔮 Задать вопрос Тарологу", "menu:question"),
        ("📆 Подбор дат", "menu:dates"),
    ]

    for user in users:
        name = user.first_name or "друг"
        text = random.choice(PUSH_MESSAGES_ACTIVE).format(name=name)
        btn_text, btn_cb = random.choice(PUSH_BUTTONS)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=btn_text, callback_data=btn_cb)],
            [InlineKeyboardButton(text="🔮 Меню", callback_data="menu:main")],
        ])
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

    async def _business_reminders():
        await _send_business_reminders(bot, session_maker)

    # Ежедневные пуши в 9:00 МСК
    scheduler.add_job(_daily_push, CronTrigger(hour=6, minute=0))
    # Напоминания об окончании подписки в 12:00 МСК
    scheduler.add_job(_reminders, CronTrigger(hour=9, minute=0))
    # Retention push — каждые 10 минут (проверяет 24ч неактивности)
    scheduler.add_job(_retention, CronTrigger(minute="*/10"))
    # Trial upsell — каждые 5 минут (проверяет 1ч неактивности для free)
    scheduler.add_job(_trial_upsell, CronTrigger(minute="*/5"))
    # Business dialog: напоминание неоплатившим (1ч, 1 раз)
    scheduler.add_job(_business_reminders, CronTrigger(minute="*/15"))

    return scheduler


async def _send_business_reminders(bot: Bot, session_maker) -> None:
    """Отправить reminder пользователям business-диалога не оплатившим через 1ч."""
    import logging
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    try:
        from bot.business_dialog.models import BusinessSession, BusinessProfile
        from bot.business_dialog.session_manager import get_biz_conn
        from bot.business_dialog.tribute_flow import return_payment_keyboard

        threshold = datetime.now(timezone.utc) - timedelta(hours=1)

        async with session_maker() as session:
            result = await session.execute(
                select(BusinessSession, BusinessProfile)
                .join(
                    BusinessProfile,
                    BusinessProfile.telegram_id == BusinessSession.telegram_id,
                    isouter=True,
                )
                .where(
                    BusinessSession.status == "free",
                    BusinessSession.reminder_sent == False,  # noqa: E712
                    BusinessSession.updated_at <= threshold,
                )
            )
            rows = result.all()

            for biz_sess, profile in rows:
                tid  = biz_sess.telegram_id
                name = profile.name if profile else "друг"
                biz_conn_id = await get_biz_conn(tid)

                text = (
                    f"{name}, я оставила твой разбор открытым 🌙\n\n"
                    f"Если почувствуешь, что готова — можешь вернуться и спокойно продолжить просмотр."
                )
                try:
                    send_kw: dict = {
                        "chat_id": tid, "text": text,
                        "parse_mode": None,
                        "reply_markup": return_payment_keyboard(),
                    }
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)
                    biz_sess.reminder_sent = True
                    await session.commit()
                    logger.info("Business reminder sent to %s", tid)
                except Exception as e:
                    logger.warning("Business reminder failed for %s: %s", tid, e)
    except Exception as e:
        logger.warning("_send_business_reminders error: %s", e)
