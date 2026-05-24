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

    async def _business_second_reminders():
        await _send_second_business_reminders(bot, session_maker)

    async def _business_abandoned():
        await _send_abandoned_reminders(bot, session_maker)

    # Ежедневные пуши в 9:00 МСК
    scheduler.add_job(_daily_push, CronTrigger(hour=6, minute=0))
    # Напоминания об окончании подписки в 12:00 МСК
    scheduler.add_job(_reminders, CronTrigger(hour=9, minute=0))
    # Retention push — каждые 10 минут (проверяет 24ч неактивности)
    scheduler.add_job(_retention, CronTrigger(minute="*/10"))
    # Trial upsell — каждые 5 минут (проверяет 1ч неактивности для free)
    scheduler.add_job(_trial_upsell, CronTrigger(minute="*/5"))
    # Business dialog: 1й reminder неоплатившим через 1ч (с кнопкой)
    scheduler.add_job(_business_reminders, CronTrigger(minute="*/15"))
    # Business dialog: 2й reminder через 24ч после первого (без кнопки)
    scheduler.add_job(_business_second_reminders, CronTrigger(minute="*/30"))
    # Business dialog: пуш для брошенных диалогов через 3ч тишины
    scheduler.add_job(_business_abandoned, CronTrigger(minute="*/30"))

    return scheduler


async def _send_business_reminders(bot: Bot, session_maker) -> None:
    """Отправить reminder пользователям которым была показана ссылка оплаты, но не оплатили (через 1ч).
    Кнопка оплаты включается только здесь — в диалоге она больше не дублируется."""
    import logging
    import time
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    try:
        from bot.business_dialog.models import BusinessSession, BusinessProfile
        from bot.business_dialog.session_manager import (
            get_biz_conn, get_payment_offered_at, get_biz_stage, get_profile,
        )
        from bot.business_dialog.tribute_flow import return_payment_keyboard, payment_keyboard

        one_hour_ago = int(time.time()) - 3600

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
                )
            )
            rows = result.all()

            for biz_sess, profile in rows:
                tid = biz_sess.telegram_id

                # Напоминание только если ссылка на оплату уже была показана и прошёл 1 час
                offered_at = await get_payment_offered_at(tid)
                if not offered_at or offered_at > one_hour_ago:
                    continue

                # Определяем стадию и нужную кнопку
                stage        = await get_biz_stage(tid)
                redis_profile = await get_profile(tid)
                name         = (profile.name if profile else None) or redis_profile.get("name") or "душа моя"
                biz_conn_id  = await get_biz_conn(tid)

                _REMINDER_TEXTS = [
                    f"{name}, я оставила ваш разбор открытым 🌙\n\nКогда почувствуете, что готовы — просто нажмите кнопку.",
                    f"Хочу, чтобы вы знали — ваш разбор ещё ждёт вас, {name} ✨\n\nМожете вернуться в любой момент.",
                    f"{name}, я никуда не ухожу 💫\n\nКогда будете готовы — просто нажмите кнопку, и я сразу начну.",
                ]
                text = random.choice(_REMINDER_TEXTS)

                # Кнопка зависит от стадии: waiting_payment → t190, waiting_upsell → следующий тир
                if stage == "waiting_upsell":
                    next_tier_key = redis_profile.get("next_tier", "t490")
                    kb = payment_keyboard(next_tier_key)
                else:
                    kb = return_payment_keyboard("t190")

                try:
                    send_kw: dict = {
                        "chat_id":      tid,
                        "text":         text,
                        "parse_mode":   None,
                        "reply_markup": kb,
                    }
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)
                    biz_sess.reminder_sent = True
                    await session.commit()
                    logger.info("Business reminder sent to %s (stage=%s)", tid, stage)
                except Exception as e:
                    logger.warning("Business reminder failed for %s: %s", tid, e)
    except Exception as e:
        logger.warning("_send_business_reminders error: %s", e)


async def _send_second_business_reminders(bot: Bot, session_maker) -> None:
    """Второй пуш через 24ч после первого напоминания — без кнопки, тёплый текст.
    Только если пользователь так и не оплатил и молчит больше 24 часов."""
    import logging
    import time
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    _SECOND_REMINDER_TEXTS = [
        "{name}, я всё ещё здесь 🌙\n\nВаша ситуация не выходит у меня из головы. Если почувствуете, что готовы продолжить — я рядом.",
        "Думаю о вас, {name} ✨\n\nИногда нужно время, чтобы решиться. Я никуда не тороплюсь — буду здесь когда будете готовы.",
        "{name}, я не забыла о вас 💫\n\nТо, что вы рассказали — важно. Когда захотите продолжить, просто напишите.",
        "Бывает, что жизнь отвлекает, {name} 🌟\n\nЯ здесь, если захотите вернуться к нашему разговору.",
    ]

    try:
        from bot.business_dialog.models import BusinessSession, BusinessProfile
        from bot.business_dialog.session_manager import (
            get_biz_conn, get_last_activity, get_profile,
        )

        now           = int(time.time())
        one_day_ago   = now - 86400
        one_hour_ago  = now - 3600

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
                    BusinessSession.reminder_sent == True,  # noqa: E712 — первый уже был
                )
            )
            rows = result.all()

            for biz_sess, profile in rows:
                tid = biz_sess.telegram_id

                # Последняя активность должна быть > 24ч назад
                last_active = await get_last_activity(tid)
                if last_active and last_active > one_day_ago:
                    continue  # ещё активен недавно

                # Первый reminder должен быть показан > 1ч назад (уже точно видел)
                from bot.business_dialog.session_manager import get_payment_offered_at
                offered_at = await get_payment_offered_at(tid)
                if not offered_at or offered_at > one_day_ago:
                    continue  # не прошли сутки с предложения

                # Деdup: один второй reminder в сутки
                from bot.services.cache import get_redis
                r = await get_redis()
                dedup_key = f"biz_reminder2:{tid}"
                already = not await r.set(dedup_key, "1", nx=True, ex=86400 * 3)
                if already:
                    continue

                redis_profile = await get_profile(tid)
                name          = (profile.name if profile else None) or redis_profile.get("name") or "душа моя"
                biz_conn_id   = await get_biz_conn(tid)

                text = random.choice(_SECOND_REMINDER_TEXTS).format(name=name)

                try:
                    send_kw: dict = {"chat_id": tid, "text": text, "parse_mode": None}
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)
                    logger.info("Second business reminder sent to %s", tid)
                except Exception as e:
                    logger.warning("Second reminder failed for %s: %s", tid, e)

    except Exception as e:
        logger.warning("_send_second_business_reminders error: %s", e)


async def _send_abandoned_reminders(bot: Bot, session_maker) -> None:
    """Пуш для брошенных диалогов — человек начал, но исчез на 3+ часов.
    Стадия: сбор данных или бесплатный диалог. Без кнопки, тёплый контекстный текст."""
    import logging
    import time
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    # Стадии = человек ещё не дошёл до предложения оплаты
    _ABANDONED_STAGES = {
        "collecting_name", "collecting_birth_date",
        "collecting_city", "collecting_problem", "free_dialog",
    }

    # Тексты для тех у кого есть имя (дошли до free_dialog или дальше сбора)
    _TEXTS_WITH_NAME = [
        "{name}, вы куда-то пропали 🌙\n\nМы только начали — и я чувствую, что в вашей ситуации есть что-то важное. Возвращайтесь когда будете готовы.",
        "Вспомнила о вас, {name} ✨\n\nМы остановились на самом интересном месте. Если захотите продолжить — просто напишите.",
        "{name}, я вас жду 💫\n\nТо, что вы рассказали — важно. Готова продолжить когда вы будете готовы.",
    ]

    # Тексты для тех кто не успел назвать имя
    _TEXTS_NO_NAME = [
        "Вы куда-то пропали 🌙\n\nЕсли хотите — можем продолжить наш разговор. Я здесь.",
        "Помню, что вы заходили ✨\n\nЕсли что-то отвлекло — не страшно. Возвращайтесь когда будете готовы.",
        "Я всё ещё здесь 💫\n\nЕсли хотите поговорить — просто напишите, продолжим с того места где остановились.",
    ]

    try:
        from bot.business_dialog.models import BusinessSession, BusinessProfile
        from bot.business_dialog.session_manager import (
            get_biz_conn, get_biz_stage, get_last_activity, get_profile,
        )
        from bot.services.cache import get_redis

        now            = int(time.time())
        three_hours_ago = now - 10800   # 3 часа

        async with session_maker() as session:
            result = await session.execute(
                select(BusinessSession, BusinessProfile)
                .join(
                    BusinessProfile,
                    BusinessProfile.telegram_id == BusinessSession.telegram_id,
                    isouter=True,
                )
                .where(BusinessSession.status == "free")
            )
            rows = result.all()

            r = await get_redis()

            for biz_sess, profile in rows:
                tid = biz_sess.telegram_id

                # Проверяем реальную стадию из Redis
                stage = await get_biz_stage(tid)
                if stage not in _ABANDONED_STAGES:
                    continue

                # Молчит > 3 часов
                last_active = await get_last_activity(tid)
                if not last_active or last_active > three_hours_ago:
                    continue

                # Деdup: один abandoned-пуш на пользователя (раз в 3 дня)
                dedup_key = f"biz_abandoned:{tid}"
                already = not await r.set(dedup_key, "1", nx=True, ex=86400 * 3)
                if already:
                    continue

                redis_profile = await get_profile(tid)
                name          = (profile.name if profile else None) or redis_profile.get("name")
                biz_conn_id   = await get_biz_conn(tid)

                if name:
                    text = random.choice(_TEXTS_WITH_NAME).format(name=name)
                else:
                    text = random.choice(_TEXTS_NO_NAME)

                try:
                    send_kw: dict = {"chat_id": tid, "text": text, "parse_mode": None}
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)
                    logger.info("Abandoned reminder sent to %s (stage=%s)", tid, stage)
                except Exception as e:
                    logger.warning("Abandoned reminder failed for %s: %s", tid, e)

    except Exception as e:
        logger.warning("_send_abandoned_reminders error: %s", e)
