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
        ("🔮 Задать вопрос Бабушке Aisha", "menu:question"),
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

    async def _followup_reminders():
        await _send_followup_reminders(bot, session_maker)

    async def _accompaniment_morning():
        await _send_accompaniment_morning_plans(bot, session_maker)

    async def _vk_reminders():
        await _send_vk_business_reminders()

    async def _vk_second_reminders():
        await _send_vk_second_reminders()

    async def _vk_abandoned():
        await _send_vk_abandoned_reminders()

    async def _vk_followup():
        await _send_vk_followup_reminders()

    async def _vk_morning():
        await _send_vk_accompaniment_morning()

    # ── Новые пуши бизнес-чата ────────────────────────────────────────────────
    async def _biz_push_unpaid():
        await _send_biz_push_unpaid(bot)

    async def _biz_morning_paid():
        await _send_biz_morning_paid(bot)

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
    # Followup: напомнить что остались вопросы (24ч тишины, макс 2 пуша)
    scheduler.add_job(_followup_reminders, CronTrigger(minute=0))
    # Сопровождение: утреннее послание в 8:00 по местному времени пользователя
    # Запускается каждый час — внутри проверяем у кого сейчас local_hour == 8
    scheduler.add_job(_accompaniment_morning, CronTrigger(minute=0))

    # Утренний привет платным (7:00 МСК = 04:00 UTC)
    scheduler.add_job(_biz_morning_paid, CronTrigger(hour=4, minute=0))
    # Пуши неплатным — каждые 15 минут проверяем 1ч/3ч/24ч молчания
    scheduler.add_job(_biz_push_unpaid, CronTrigger(minute="*/15"))

    # ── VK пуши (аналог TG business пушей) ───────────────────────────────────
    scheduler.add_job(_vk_reminders,        CronTrigger(minute="*/15"))
    scheduler.add_job(_vk_second_reminders, CronTrigger(minute="*/30"))
    scheduler.add_job(_vk_abandoned,        CronTrigger(minute="*/30"))
    scheduler.add_job(_vk_followup,         CronTrigger(minute=0))
    scheduler.add_job(_vk_morning,          CronTrigger(minute=0))

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
                    kb = payment_keyboard(tid, next_tier_key)
                else:
                    kb = return_payment_keyboard(tid, "t190")

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


async def _send_followup_reminders(bot: Bot, session_maker) -> None:
    """Напомнить followup-пользователям что у них остались вопросы.

    Условия срабатывания:
    — stage == "followup"
    — followup_left > 0 (вопросы ещё есть)
    — молчит 24ч+
    — пушей отправлено < 2 (счётчик сбрасывается когда пользователь пишет)

    Текст — короткий AI-пуш на основе профиля и проблемы клиента.
    """
    import logging
    import json
    import time
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    try:
        from bot.business_dialog.models import BusinessSession
        from bot.business_dialog.session_manager import (
            get_biz_conn, get_biz_stage, get_profile,
            get_last_activity, get_followup_left,
        )
        from bot.business_dialog.services import generate_business
        from bot.business_dialog.prompts import AISHA_FREE_PROMPT
        from bot.services.cache import get_redis

        r            = await get_redis()
        one_day_ago  = int(time.time()) - 86400

        async with session_maker() as session:
            result = await session.execute(
                select(BusinessSession).where(BusinessSession.status == "paid")
            )
            sessions = result.scalars().all()

            for biz_sess in sessions:
                tid = biz_sess.telegram_id

                # Только стадия followup
                stage = await get_biz_stage(tid)
                if stage != "followup":
                    continue

                # Ещё есть вопросы
                left = await get_followup_left(tid)
                if not left or left <= 0:
                    continue

                # Молчит 24ч+
                last_active = await get_last_activity(tid)
                if not last_active or last_active > one_day_ago:
                    continue

                # Не более 2 пушей за эту «сессию молчания»
                push_count_key = f"followup_push_count:{tid}"
                push_count     = int(await r.get(push_count_key) or 0)
                if push_count >= 2:
                    continue

                # Дедупликация — один пуш в 24ч
                dedup_key = f"followup_push_dedup:{tid}"
                already   = not await r.set(dedup_key, "1", nx=True, ex=86400)
                if already:
                    continue

                profile     = await get_profile(tid)
                biz_conn_id = await get_biz_conn(tid)
                name        = profile.get("name", "")

                context = json.dumps({
                    "name":          name,
                    "gender":        profile.get("gender", "unknown"),
                    "problem":       profile.get("problem", ""),
                    "followup_left": left,
                }, ensure_ascii=False)

                try:
                    reminder = await generate_business(
                        AISHA_FREE_PROMPT,
                        f"Клиент получил консультацию. У него ещё осталось {left} уточняющих вопроса "
                        f"которые он не задал — и он молчит больше суток.\n\n"
                        f"Напиши ОЧЕНЬ короткое напоминание (1–2 предложения максимум).\n"
                        f"Намекни что ты всё ещё думаешь об их ситуации и готова ответить.\n"
                        f"Говори тепло, без давления. Обращайся на вы.\n"
                        f"НЕ упоминай число вопросов, деньги и оплату.\n"
                        f"НЕ задавай вопросов в конце — только тёплый импульс вернуться.\n\n"
                        f"Данные: {context}",
                        complexity="simple",
                        max_tokens=55,
                    )

                    send_kw: dict = {"chat_id": tid, "text": reminder, "parse_mode": None}
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)

                    # Увеличиваем счётчик пушей (TTL 14 дней — пока не ответит)
                    new_count = await r.incr(push_count_key)
                    if new_count == 1:
                        await r.expire(push_count_key, 86400 * 14)

                    logger.info(
                        "Followup reminder #%d sent to %s (left=%d questions)",
                        new_count, tid, left,
                    )

                except Exception as e:
                    logger.warning("Followup reminder failed for %s: %s", tid, e)

    except Exception as e:
        logger.warning("_send_followup_reminders error: %s", e)


async def _send_accompaniment_morning_plans(bot: Bot, session_maker) -> None:
    """Утреннее послание сопровождаемым пользователям — в 8:00 по местному времени.

    Запускается каждый час. Для каждого пользователя проверяем:
    UTC_hour + tz_offset == 8 → сейчас его утро, отправляем план.
    Погрешность 0–12 минут — чтобы план приходил не ровно в 8:00 и было ожидание.
    """
    import asyncio
    import logging
    import json
    from datetime import datetime, timezone, date
    from sqlalchemy import select
    logger = logging.getLogger(__name__)

    try:
        from bot.business_dialog.models import BusinessSession
        from bot.business_dialog.session_manager import (
            get_biz_conn, get_biz_stage, get_profile,
        )
        from bot.business_dialog.services import generate_business
        from bot.business_dialog.prompts import AISHA_MORNING_PLAN_PROMPT
        from bot.services.cache import get_redis

        utc_hour = datetime.now(timezone.utc).hour
        today    = date.today().isoformat()
        r        = await get_redis()

        async with session_maker() as session:
            result = await session.execute(
                select(BusinessSession).where(BusinessSession.status == "paid")
            )
            sessions = result.scalars().all()

            for biz_sess in sessions:
                tid = biz_sess.telegram_id

                # Проверяем стадию из Redis — только "accompaniment"
                stage = await get_biz_stage(tid)
                if stage != "accompaniment":
                    continue

                # Проверяем локальный час пользователя
                profile    = await get_profile(tid)
                tz_offset  = int(profile.get("tz_offset", 3))   # fallback МСК
                local_hour = (utc_hour + tz_offset) % 24
                if local_hour != 8:
                    continue  # не его утро — пропускаем

                # Дедупликация — один утренний план в день
                plan_key = f"morning_plan:{tid}:{today}"
                already  = not await r.set(plan_key, "1", nx=True, ex=86400)
                if already:
                    continue

                biz_conn_id = await get_biz_conn(tid)

                context = json.dumps({
                    "name":       profile.get("name", ""),
                    "gender":     profile.get("gender", "unknown"),
                    "birth_date": profile.get("birth_date", ""),
                    "problem":    profile.get("problem", ""),
                    "date":       today,
                }, ensure_ascii=False)

                try:
                    # Погрешность 0–12 минут — план приходит в промежутке 8:00–8:12,
                    # создаёт приятное ожидание вместо точного автоматного тика
                    delay = random.randint(0, 720)
                    await asyncio.sleep(delay)

                    plan = await generate_business(
                        AISHA_MORNING_PLAN_PROMPT,
                        f"Данные клиента: {context}",
                        complexity="medium",
                        max_tokens=350,
                    )

                    send_kw: dict = {"chat_id": tid, "text": plan, "parse_mode": None}
                    if biz_conn_id:
                        send_kw["business_connection_id"] = biz_conn_id
                    await bot.send_message(**send_kw)
                    logger.info(
                        "Morning plan sent to %s (tz=UTC+%d, delay=%ds)",
                        tid, tz_offset, delay,
                    )

                except Exception as e:
                    logger.warning("Morning plan failed for %s: %s", tid, e)

    except Exception as e:
        logger.warning("_send_accompaniment_morning_plans error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# VK ПУШИ — аналог TG business пушей
# ═══════════════════════════════════════════════════════════════════════════════

async def _vk_send(vk_api, uid: int, text: str) -> bool:
    """Отправить сообщение VK-пользователю. Возвращает True если успешно."""
    import random as _random
    try:
        await vk_api.messages.send(peer_id=uid, message=text, random_id=_random.randint(1, 2**31))
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("VK push failed for %s: %s", uid, e)
        return False


async def _send_vk_business_reminders() -> None:
    """1й reminder: ссылка оплаты показана, но не оплатили — через 1ч."""
    import logging
    import time
    logger = logging.getLogger(__name__)

    from bot.vk_dialog.router import get_vk_api
    from bot.vk_dialog.session_manager import (
        get_all_user_ids, get_stage, get_profile,
        get_payment_offered_at, get_last_activity,
        get_vk_reminder_sent, set_vk_reminder_sent,
    )
    from bot.vk_dialog.payments import create_payment_link
    from bot.business_dialog.upsell import get_tier

    vk_api = get_vk_api()
    if vk_api is None:
        return

    _TEXTS = [
        "{name}, я оставила ваш разбор открытым 🌙\n\nКогда почувствуете, что готовы — просто перейдите по ссылке.",
        "Хочу, чтобы вы знали — ваш разбор ещё ждёт вас, {name} ✨\n\nМожете вернуться в любой момент.",
        "{name}, я никуда не ухожу 💫\n\nКогда будете готовы — просто перейдите по ссылке, и я сразу начну.",
    ]

    one_hour_ago = int(time.time()) - 3600
    uids = await get_all_user_ids()

    for uid in uids:
        try:
            stage = await get_stage(uid)
            if stage not in ("waiting_payment", "waiting_upsell"):
                continue

            offered_at = await get_payment_offered_at(uid)
            if not offered_at or offered_at > one_hour_ago:
                continue

            if await get_vk_reminder_sent(uid):
                continue

            profile   = await get_profile(uid)
            name      = profile.get("name") or "душа моя"
            tier_key  = profile.get("next_tier") or "t190"

            try:
                link = create_payment_link(uid, tier_key)
                tier = get_tier(tier_key)
                price = tier.get("price", 190)
                tname = tier.get("name", "Разбор")
                link_line = f"\n\n✨ «{tname}» — {price} ₽\n{link}"
            except Exception:
                link_line = ""

            text = random.choice(_TEXTS).format(name=name) + link_line
            if await _vk_send(vk_api, uid, text):
                await set_vk_reminder_sent(uid)
                logger.info("VK reminder sent to %s (stage=%s)", uid, stage)
        except Exception as e:
            logger.warning("VK reminder error for %s: %s", uid, e)


async def _send_vk_second_reminders() -> None:
    """2й reminder: 24ч тишины после первого — тёплый текст без ссылки."""
    import logging
    import time
    logger = logging.getLogger(__name__)

    from bot.vk_dialog.router import get_vk_api
    from bot.vk_dialog.session_manager import (
        get_all_user_ids, get_stage, get_profile,
        get_last_activity, get_payment_offered_at,
        get_vk_reminder_sent,
    )
    from bot.services.cache import get_redis

    vk_api = get_vk_api()
    if vk_api is None:
        return

    _TEXTS = [
        "{name}, я всё ещё здесь 🌙\n\nВаша ситуация не выходит у меня из головы. Если почувствуете, что готовы продолжить — я рядом.",
        "Думаю о вас, {name} ✨\n\nИногда нужно время, чтобы решиться. Я никуда не тороплюсь — буду здесь когда будете готовы.",
        "{name}, я не забыла о вас 💫\n\nТо, что вы рассказали — важно. Когда захотите продолжить, просто напишите.",
    ]

    now          = int(time.time())
    one_day_ago  = now - 86400
    r            = await get_redis()
    uids         = await get_all_user_ids()

    for uid in uids:
        try:
            stage = await get_stage(uid)
            if stage not in ("waiting_payment", "waiting_upsell"):
                continue

            if not await get_vk_reminder_sent(uid):
                continue  # первый ещё не был

            last_active = await get_last_activity(uid)
            if not last_active or last_active > one_day_ago:
                continue

            offered_at = await get_payment_offered_at(uid)
            if not offered_at or offered_at > one_day_ago:
                continue

            dedup_key = f"vk:reminder2:{uid}"
            if not await r.set(dedup_key, "1", nx=True, ex=86400 * 3):
                continue

            profile = await get_profile(uid)
            name    = profile.get("name") or "душа моя"
            text    = random.choice(_TEXTS).format(name=name)

            if await _vk_send(vk_api, uid, text):
                logger.info("VK second reminder sent to %s", uid)
        except Exception as e:
            logger.warning("VK second reminder error for %s: %s", uid, e)


async def _send_vk_abandoned_reminders() -> None:
    """Пуш для брошенных диалогов — 3ч тишины на ранних стадиях."""
    import logging
    import time
    logger = logging.getLogger(__name__)

    from bot.vk_dialog.router import get_vk_api
    from bot.vk_dialog.session_manager import (
        get_all_user_ids, get_stage, get_profile, get_last_activity,
    )
    from bot.services.cache import get_redis

    vk_api = get_vk_api()
    if vk_api is None:
        return

    _ABANDONED_STAGES = {"collecting_name", "collecting_birth_date", "collecting_city", "collecting_problem", "free_dialog"}

    _TEXTS_WITH_NAME = [
        "{name}, вы куда-то пропали 🌙\n\nМы только начали — и я чувствую, что в вашей ситуации есть что-то важное. Возвращайтесь когда будете готовы.",
        "Вспомнила о вас, {name} ✨\n\nМы остановились на самом интересном месте. Если захотите продолжить — просто напишите.",
    ]
    _TEXTS_NO_NAME = [
        "Вы куда-то пропали 🌙\n\nЕсли хотите — можем продолжить наш разговор. Я здесь.",
        "Помню, что вы заходили ✨\n\nЕсли что-то отвлекло — не страшно. Возвращайтесь когда будете готовы.",
    ]

    three_hours_ago = int(time.time()) - 10800
    r               = await get_redis()
    uids            = await get_all_user_ids()

    for uid in uids:
        try:
            stage = await get_stage(uid)
            if stage not in _ABANDONED_STAGES:
                continue

            last_active = await get_last_activity(uid)
            if not last_active or last_active > three_hours_ago:
                continue

            dedup_key = f"vk:abandoned:{uid}"
            if not await r.set(dedup_key, "1", nx=True, ex=86400 * 3):
                continue

            profile = await get_profile(uid)
            name    = profile.get("name")
            text    = (random.choice(_TEXTS_WITH_NAME).format(name=name) if name
                       else random.choice(_TEXTS_NO_NAME))

            if await _vk_send(vk_api, uid, text):
                logger.info("VK abandoned reminder sent to %s (stage=%s)", uid, stage)
        except Exception as e:
            logger.warning("VK abandoned error for %s: %s", uid, e)


async def _send_vk_followup_reminders() -> None:
    """Followup-пуш: остались вопросы, молчит 24ч+, макс 2 пуша."""
    import logging
    import json
    import time
    logger = logging.getLogger(__name__)

    from bot.vk_dialog.router import get_vk_api
    from bot.vk_dialog.session_manager import (
        get_all_user_ids, get_stage, get_profile,
        get_last_activity, get_followup_left,
    )
    from bot.business_dialog.services import generate_business
    from bot.business_dialog.prompts import AISHA_FREE_PROMPT
    from bot.services.cache import get_redis

    vk_api      = get_vk_api()
    if vk_api is None:
        return

    one_day_ago = int(time.time()) - 86400
    r           = await get_redis()
    uids        = await get_all_user_ids()

    for uid in uids:
        try:
            if await get_stage(uid) != "followup":
                continue

            left = await get_followup_left(uid)
            if not left or left <= 0:
                continue

            last_active = await get_last_activity(uid)
            if not last_active or last_active > one_day_ago:
                continue

            push_count_key = f"vk:followup_push_count:{uid}"
            push_count     = int(await r.get(push_count_key) or 0)
            if push_count >= 2:
                continue

            dedup_key = f"vk:followup_push_dedup:{uid}"
            if not await r.set(dedup_key, "1", nx=True, ex=86400):
                continue

            profile = await get_profile(uid)
            name    = profile.get("name", "")
            context = json.dumps({
                "name":          name,
                "gender":        profile.get("gender", "unknown"),
                "problem":       profile.get("problem", ""),
                "followup_left": left,
            }, ensure_ascii=False)

            reminder = await generate_business(
                AISHA_FREE_PROMPT,
                f"Клиент получил консультацию. У него ещё осталось {left} уточняющих вопроса "
                f"которые он не задал — и он молчит больше суток.\n\n"
                f"Напиши ОЧЕНЬ короткое напоминание (1–2 предложения максимум).\n"
                f"Намекни что ты всё ещё думаешь об их ситуации и готова ответить.\n"
                f"Говори тепло, без давления. Обращайся на вы.\n"
                f"НЕ упоминай число вопросов, деньги и оплату.\n"
                f"НЕ задавай вопросов в конце — только тёплый импульс вернуться.\n\n"
                f"Данные: {context}",
                complexity="simple", max_tokens=55,
            )

            if await _vk_send(vk_api, uid, reminder):
                new_count = await r.incr(push_count_key)
                if new_count == 1:
                    await r.expire(push_count_key, 86400 * 14)
                logger.info("VK followup reminder #%d sent to %s", new_count, uid)
        except Exception as e:
            logger.warning("VK followup error for %s: %s", uid, e)


async def _send_vk_accompaniment_morning() -> None:
    """Утреннее послание VK-сопровождаемым в 8:00 по местному времени."""
    import logging
    import json
    import asyncio
    from datetime import datetime, timezone, date
    logger = logging.getLogger(__name__)

    from bot.vk_dialog.router import get_vk_api
    from bot.vk_dialog.session_manager import (
        get_all_user_ids, get_stage, get_profile,
    )
    from bot.business_dialog.services import generate_business
    from bot.business_dialog.prompts import AISHA_MORNING_PLAN_PROMPT
    from bot.services.cache import get_redis

    vk_api   = get_vk_api()
    if vk_api is None:
        return

    utc_hour = datetime.now(timezone.utc).hour
    today    = date.today().isoformat()
    r        = await get_redis()
    uids     = await get_all_user_ids()

    for uid in uids:
        try:
            if await get_stage(uid) != "accompaniment":
                continue

            profile    = await get_profile(uid)
            tz_offset  = int(profile.get("tz_offset", 3))
            local_hour = (utc_hour + tz_offset) % 24
            if local_hour != 8:
                continue

            plan_key = f"vk:morning_plan:{uid}:{today}"
            if not await r.set(plan_key, "1", nx=True, ex=86400):
                continue

            context = json.dumps({
                "name":       profile.get("name", ""),
                "gender":     profile.get("gender", "unknown"),
                "birth_date": profile.get("birth_date", ""),
                "problem":    profile.get("problem", ""),
                "date":       today,
            }, ensure_ascii=False)

            delay = random.randint(0, 720)
            await asyncio.sleep(delay)

            plan = await generate_business(
                AISHA_MORNING_PLAN_PROMPT,
                f"Данные клиента: {context}",
                complexity="medium", max_tokens=350,
            )

            if await _vk_send(vk_api, uid, plan):
                logger.info("VK morning plan sent to %s (tz=UTC+%d)", uid, tz_offset)
        except Exception as e:
            logger.warning("VK morning plan error for %s: %s", uid, e)


# ═══════════════════════════════════════════════════════════════════════════════
# НОВЫЕ ПУШИ БИЗНЕС-ЧАТА (TG) — monthly_990
# ═══════════════════════════════════════════════════════════════════════════════

_BIZ_PUSH_1 = [
    "{name}, вы написали мне вопрос, и я ответила вам 🌙\n\nЕсли хотите продолжить работу со мной — я здесь.",
    "Думаю о вашем вопросе, {name} ✨\n\nЕсли хотите работать со мной каждый день — подписка открыта.",
]
_BIZ_PUSH_2 = [
    "{name}, иногда нужно время чтобы осмыслить ✨\n\nКогда будете готовы продолжить — просто напишите.",
    "Душа моя, {name} — я всё ещё здесь 🌙\n\nГотова работать с вами каждый день весь месяц.",
]
_BIZ_PUSH_3 = [
    "Думаю о вас, {name} 💫\n\nЕсли остались вопросы — я готова работать с вами весь месяц.",
    "{name}, один вопрос только открывает дверь 🌙\n\nЗа ней — целый месяц работы со мной. Жду вас.",
]

_MORNING_FEMALE_BIZ = [
    "Доброе утро, моя хорошая 🌙\n\nНовый день — новые возможности. Что сегодня лежит на сердце?",
    "С добрым утром, душа моя ✨\n\nЯ здесь и готова слушать. Чем могу помочь сегодня?",
    "Доброе утро, голубушка 🌟\n\nКак вы? Я готова к вашим вопросам.",
]
_MORNING_MALE_BIZ = [
    "Доброе утро, мой хороший 🌙\n\nНовый день — новые возможности. Что сегодня лежит на сердце?",
    "С добрым утром, душа моя ✨\n\nЯ здесь и готова слушать. Чем могу помочь сегодня?",
    "Доброе утро, голубчик 🌟\n\nКак вы? Я готова к вашим вопросам.",
]


async def _send_biz_push_unpaid(bot) -> None:
    """Пуши для неоплативших: 1ч → push#1, 3ч → push#2, 24ч → push#3."""
    import logging, time
    logger = logging.getLogger(__name__)
    try:
        from bot.business_dialog.session_manager import (
            get_biz_stage, get_biz_conn, get_last_activity, get_profile,
        )
        from bot.business_dialog.tribute_flow import _session_maker, create_tg_business_payment_link
        from bot.business_dialog.models import BusinessSession
        from bot.services.cache import get_redis
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from sqlalchemy import select

        if not _session_maker:
            return
        r   = await get_redis()
        now = int(time.time())
        async with _session_maker() as session:
            rows = (await session.execute(
                select(BusinessSession).where(BusinessSession.status == "free")
            )).scalars().all()
        for biz_sess in rows:
            tid = biz_sess.telegram_id
            try:
                stage = await get_biz_stage(tid)
                if stage not in ("answered", "waiting_payment"):
                    continue
                last = await get_last_activity(tid)
                if not last:
                    continue
                elapsed    = now - last
                push_key   = f"biz:new_push:{tid}"
                push_count = int(await r.get(push_key) or 0)
                if push_count >= 3:
                    continue
                push_texts = [_BIZ_PUSH_1, _BIZ_PUSH_2, _BIZ_PUSH_3]
                thresholds = [3600, 10800, 86400]
                if elapsed < thresholds[push_count]:
                    continue
                dedup = f"biz:new_push_dedup:{tid}:{push_count}"
                if not await r.set(dedup, "1", nx=True, ex=86400 * 2):
                    continue
                profile = await get_profile(tid)
                name    = profile.get("name", "душа моя")
                text    = random.choice(push_texts[push_count]).format(name=name)
                biz_conn_id = await get_biz_conn(tid)
                try:
                    link = create_tg_business_payment_link(tid, "monthly_990")
                    kb   = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💎 Оформить подписку — 990 ₽", url=link)]
                    ])
                except Exception:
                    kb = None
                send_kw: dict = {"chat_id": tid, "text": text}
                if biz_conn_id:
                    send_kw["business_connection_id"] = biz_conn_id
                if kb:
                    send_kw["reply_markup"] = kb
                await bot.send_message(**send_kw)
                await r.incr(push_key)
                await r.expire(push_key, 86400 * 7)
                logger.info("Biz push #%d sent to %s", push_count + 1, tid)
            except Exception as e:
                logger.warning("Biz push error for %s: %s", tid, e)
    except Exception as e:
        logger.warning("_send_biz_push_unpaid error: %s", e)


async def _send_biz_morning_paid(bot) -> None:
    """Утренний привет платным бизнес-пользователям в 7:00–7:09 МСК."""
    import logging, asyncio as _asyncio
    from datetime import date as _date
    logger = logging.getLogger(__name__)
    try:
        from bot.business_dialog.session_manager import (
            get_biz_stage, get_biz_conn, get_profile,
        )
        from bot.business_dialog.tribute_flow import _session_maker
        from bot.business_dialog.models import BusinessSession
        from bot.services.cache import get_redis
        from sqlalchemy import select

        if not _session_maker:
            return
        today = _date.today().isoformat()
        r     = await get_redis()
        async with _session_maker() as session:
            rows = (await session.execute(
                select(BusinessSession).where(BusinessSession.status == "paid")
            )).scalars().all()
        for biz_sess in rows:
            tid = biz_sess.telegram_id
            try:
                stage = await get_biz_stage(tid)
                if stage not in ("paid_monthly", "followup", "accompaniment"):
                    continue
                dedup_key = f"biz:morning:{tid}:{today}"
                if not await r.set(dedup_key, "1", nx=True, ex=86400):
                    continue
                profile     = await get_profile(tid)
                gender      = profile.get("gender", "unknown")
                biz_conn_id = await get_biz_conn(tid)
                text  = random.choice(_MORNING_FEMALE_BIZ if gender == "female" else _MORNING_MALE_BIZ)
                delay = random.randint(0, 540)
                await _asyncio.sleep(delay)
                send_kw: dict = {"chat_id": tid, "text": text}
                if biz_conn_id:
                    send_kw["business_connection_id"] = biz_conn_id
                await bot.send_message(**send_kw)
                logger.info("Biz morning greeting sent to %s (delay=%ds)", tid, delay)
            except Exception as e:
                logger.warning("Biz morning error for %s: %s", tid, e)
    except Exception as e:
        logger.warning("_send_biz_morning_paid error: %s", e)
