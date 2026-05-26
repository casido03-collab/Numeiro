"""Гороскоп дня — рандомизированный шаблон + мистическая фраза."""
import asyncio
import random
from datetime import date, datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.data.horoscope_data import HOROSCOPE_TEMPLATES, MYSTICAL_PHRASES, get_zodiac
from bot.keyboards.main import back_to_main
from bot.utils import parse_birth_date

router = Router()

# Московское время UTC+3
_MSK = timezone(timedelta(hours=3))


def _time_until_midnight_msk() -> str:
    """Время до полуночи по московскому времени."""
    now_msk = datetime.now(_MSK)
    midnight_msk = (now_msk + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = midnight_msk - now_msk
    hours = int(delta.total_seconds()) // 3600
    minutes = (int(delta.total_seconds()) % 3600) // 60
    if hours > 0:
        return f"{hours} ч {minutes} мин"
    return f"{minutes} мин"


def _pick_horoscope(user_id: int) -> tuple[str, str]:
    """Детерминированно выбрать шаблон и мистическую фразу на сегодня."""
    today = date.today()
    seed = user_id * 31337 + today.toordinal()
    rng = random.Random(seed)
    template = rng.choice(HOROSCOPE_TEMPLATES)
    phrase = rng.choice(MYSTICAL_PHRASES)
    return template, phrase


def _after_horoscope_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 На Главную", callback_data="menu:main")],
        [InlineKeyboardButton(text="🃏 Карта Дня", callback_data="menu:tarot")],
    ])


@router.callback_query(F.data == "menu:horoscope")
async def horoscope_menu(callback: CallbackQuery, user: User, session: AsyncSession):
    today_str = date.today().strftime("%Y-%m-%d")
    cache_key = make_cache_key("horoscope", user.id, today_str)

    # ── Уже получал сегодня → показываем таймер ──────────────────────────────
    already_today = await get_cached(cache_key)
    if already_today:
        time_left = _time_until_midnight_msk()
        await callback.message.edit_text(
            f"🔯 *Гороскоп дня уже получен* — найди его выше в переписке ☝️\n\n"
            f"Следующий гороскоп откроется через *{time_left}* 🌙\n\n"
            f"_Каждый день — новое послание звёзд_",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 История", callback_data="reports:menu")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # ── Нет даты рождения ─────────────────────────────────────────────────────
    if not user.birth_date:
        await callback.message.edit_text(
            "✨ Для гороскопа нам нужна ваша дата рождения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # ── Этап 1: «Считываю вашу дату» ─────────────────────────────────────────
    await callback.message.edit_text(
        "🌙 _Считываю вашу дату..._",
        parse_mode="Markdown",
    )
    await callback.answer()
    await asyncio.sleep(3)

    # ── Этап 2: «Считываю ваш знак зодиака» ──────────────────────────────────
    birth = parse_birth_date(user.birth_date)
    if not birth:
        await callback.message.edit_text("❌ Дата рождения не распознана.")
        return

    zodiac_emoji, zodiac_name = get_zodiac(birth.day, birth.month)
    await callback.message.edit_text(
        f"🔮 _Считываю ваш знак зодиака..._\n\n_{zodiac_emoji} {zodiac_name}_",
        parse_mode="Markdown",
    )
    await asyncio.sleep(3)

    # ── Генерируем гороскоп ───────────────────────────────────────────────────
    template, phrase = _pick_horoscope(user.id)
    horoscope_text = f"{template} {phrase}"

    # Сохраняем в кэш до полуночи МСК
    now_msk = datetime.now(_MSK)
    midnight_msk = (now_msk + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    ttl = int((midnight_msk - now_msk).total_seconds())
    await set_cached(cache_key, horoscope_text, ttl=ttl)

    # Сохраняем в историю
    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "horoscope",
        title=f"Гороскоп — {zodiac_emoji} {zodiac_name} | {date.today().strftime('%d.%m.%Y')}",
        content=horoscope_text,
        metadata={"zodiac": zodiac_name, "zodiac_emoji": zodiac_emoji, "date": today_str},
    )

    # ── Финальное сообщение ───────────────────────────────────────────────────
    name = user.first_name or "друг"
    text = (
        f"🔯 *Гороскоп дня — {name}*\n"
        f"_{zodiac_emoji} {zodiac_name} | {date.today().strftime('%d.%m.%Y')}_\n\n"
        f"{horoscope_text}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=_after_horoscope_keyboard(),
        parse_mode="Markdown",
    )
