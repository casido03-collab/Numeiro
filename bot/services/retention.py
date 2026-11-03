"""Retention Push System — возврат неактивных пользователей."""
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ─── 30 push-сообщений (цикличная ротация) ───────────────────────────────────

RETENTION_PUSHES = [
    "✨ {name}, в Aisha AI доступны бесплатные гороскоп и «Энергия дня». "
    "Платные услуги и их состав можно посмотреть в меню: /start. Отключить напоминания: /stop",
    "🌙 {name}, готовые ответы сохранены в «Мои разборы» — их можно перечитать без оплаты. "
    "Открыть меню: /start. Отключить напоминания: /stop",
]

TRIAL_UPSELL_TEXT = (
    "🌙 {name}, бабушка Aisha просила передать…\n\n"
    "Иногда человек уходит именно в тот момент, когда ответы начинают становиться особенно важными.\n\n"
    "Если внутри остались вопросы — возвращайся.\n\n"
    "✨ /start"
)


def _is_push_time() -> bool:
    """Проверить что сейчас разрешённое время для retention (10:00–22:00 МСК)."""
    msk_hour = (datetime.now(timezone.utc).hour + 3) % 24
    return 10 <= msk_hour < 22


def _is_trial_upsell_time() -> bool:
    """Разрешённое время для trial upsell (7:00–23:00 МСК)."""
    msk_hour = (datetime.now(timezone.utc).hour + 3) % 24
    return 7 <= msk_hour < 23


async def run_retention_pushes(bot: Bot, session: AsyncSession) -> None:
    """Найти неактивных 24ч+ пользователей и отправить им push."""
    from config import settings
    if not settings.marketing_reminders_enabled:
        return
    if not _is_push_time():
        return

    from bot.models.user import User, UserActivity

    threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await session.execute(
        select(User, UserActivity).where(User.telegram_id.is_not(None))
        .join(UserActivity, UserActivity.user_id == User.id)
        .where(
            User.is_blocked == False,  # noqa: E712
            UserActivity.last_activity_at <= threshold,
            # Не слать повторно если уже слали менее 24ч назад
            (UserActivity.last_push_at == None) |  # noqa: E711
            (UserActivity.last_push_at <= threshold),
        )
    )
    rows = result.all()

    now = datetime.now(timezone.utc)
    for user, activity in rows:
        name = user.first_name or "друг"
        idx = activity.push_index % len(RETENTION_PUSHES)
        text = RETENTION_PUSHES[idx].format(name=name)

        try:
            await bot.send_message(user.telegram_id, text, parse_mode=None)
            activity.last_push_at = now
            activity.push_index = activity.push_index + 1
            await session.commit()
            logger.info("Retention push #%s sent to user %s", idx + 1, user.telegram_id)
        except Exception as e:
            logger.warning("Retention push failed for user %s: %s", user.telegram_id, e)


async def run_trial_upsell(bot: Bot, session: AsyncSession) -> None:
    """Отправить trial upsell один раз — free-пользователям после 1ч неактивности."""
    from config import settings
    if not settings.marketing_reminders_enabled:
        return
    if not _is_trial_upsell_time():
        return

    from bot.models.user import User, UserActivity, Subscription, PlanEnum, SubscriptionStatusEnum

    threshold = datetime.now(timezone.utc) - timedelta(hours=1)

    result = await session.execute(
        select(User, UserActivity).where(User.telegram_id.is_not(None))
        .join(UserActivity, UserActivity.user_id == User.id)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            User.is_blocked == False,  # noqa: E712
            Subscription.plan == PlanEnum.free,
            UserActivity.trial_upsell_sent == False,  # noqa: E712
            UserActivity.last_activity_at != None,  # noqa: E711  — был в боте хотя бы раз
            UserActivity.last_activity_at <= threshold,
        )
    )
    rows = result.all()

    for user, activity in rows:
        name = user.first_name or "друг"
        text = TRIAL_UPSELL_TEXT.format(name=name)
        try:
            await bot.send_message(user.telegram_id, text, parse_mode="HTML")
            activity.trial_upsell_sent = True
            await session.commit()
            logger.info("Trial upsell sent to user %s", user.telegram_id)
        except Exception as e:
            logger.warning("Trial upsell failed for user %s: %s", user.telegram_id, e)
            # Помечаем как отправленный даже при ошибке парсинга — иначе будет бесконечный retry
            if "can't parse entities" in str(e):
                activity.trial_upsell_sent = True
                await session.commit()


# ─── Onboarding nudge — 4 пуша для незавершённого онбординга ─────────────────
# Первый через 10 мин от регистрации, далее +30/+60/+120 мин от предыдущего

_ONBOARD_TEXTS = [
    (
        "🌙 Бабушка Aisha просила передать…\n\n"
        "Иногда человек уходит именно в тот момент, "
        "когда ответы начинают становиться особенно важными.\n\n"
        "Если внутри остались вопросы — возвращайтесь.\n\n"
        "✨ /start"
    ),
    (
        "🌙 Вы начали знакомство, но не завершили его.\n\n"
        "Мне нужна всего пара минут, чтобы настроить всё под Вас — "
        "дата рождения и сфера интереса.\n\n"
        "Нажмите /start — продолжим ✨"
    ),
    (
        "🔮 Ваш персональный разбор ждёт Вас.\n\n"
        "Без даты рождения я не смогу рассчитать Ваши числа "
        "и дать точный прогноз.\n\n"
        "Завершите знакомство — это займёт меньше минуты.\n\n"
        "/start"
    ),
    (
        "✨ Последнее напоминание.\n\n"
        "Сотни людей уже получили свой разбор — гороскоп, карту дня, матрицу судьбы.\n\n"
        "Всё это доступно и для Вас. Осталось только завершить знакомство.\n\n"
        "/start — и я начну 🌙"
    ),
]

_ONBOARD_FIRST_DELAY = 10
_ONBOARD_GAPS = [30, 60, 120]


async def run_onboarding_nudge(bot: Bot, session: AsyncSession) -> None:
    """Отправить пуши пользователям, не завершившим онбординг.
    Первый через 10 мин от регистрации, далее +30/+60/+120 мин от предыдущего."""
    from config import settings
    if not settings.marketing_reminders_enabled:
        return
    if not _is_push_time():
        return

    from bot.models.user import User, UserProfile
    from bot.services.cache import get_redis
    import time as _time

    r = await get_redis()
    now = datetime.now(timezone.utc)
    now_ts = int(_time.time())

    all_profiles = await session.execute(select(UserProfile.user_id, UserProfile.preferences))
    onboarded_ids = set()
    for row in all_profiles.all():
        prefs = row.preferences or {}
        if prefs.get("onboarding_done"):
            onboarded_ids.add(row.user_id)

    result = await session.execute(
        select(User).where(User.telegram_id.is_not(None),
            User.is_blocked == False,  # noqa: E712
            User.id.notin_(onboarded_ids) if onboarded_ids else User.id.isnot(None),
        )
    )
    users = result.scalars().all()

    for user in users:
        if not user.created_at:
            continue

        idx_key = f"onboard_idx:{user.id}"
        ts_key = f"onboard_last_ts:{user.id}"

        idx_raw = await r.get(idx_key)
        idx = int(idx_raw) if idx_raw else 0

        if idx >= len(_ONBOARD_TEXTS):
            continue

        if idx == 0:
            minutes_since_reg = (now - user.created_at).total_seconds() / 60
            if minutes_since_reg < _ONBOARD_FIRST_DELAY:
                continue
        else:
            last_ts_raw = await r.get(ts_key)
            if not last_ts_raw:
                continue
            gap = _ONBOARD_GAPS[idx - 1] if idx - 1 < len(_ONBOARD_GAPS) else 120
            minutes_since_last = (now_ts - int(last_ts_raw)) / 60
            if minutes_since_last < gap:
                continue

        text = _ONBOARD_TEXTS[idx]
        try:
            await bot.send_message(user.telegram_id, text)
            await r.set(idx_key, str(idx + 1), ex=86400 * 30)
            await r.set(ts_key, str(now_ts), ex=86400 * 30)
            logger.info("Onboarding nudge #%s sent to user %s", idx + 1, user.telegram_id)
        except Exception as e:
            await r.set(idx_key, str(idx + 1), ex=86400 * 30)
            await r.set(ts_key, str(now_ts), ex=86400 * 30)
            logger.warning("Onboarding nudge failed for user %s: %s", user.telegram_id, e)
