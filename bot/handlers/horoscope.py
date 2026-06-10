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


_ZODIAC_NAMES: dict[str, dict[str, str]] = {
    "Овен":      {"en": "Aries",       "fa": "حمل",    "tr": "Koç"},
    "Телец":     {"en": "Taurus",      "fa": "ثور",    "tr": "Boğa"},
    "Близнецы":  {"en": "Gemini",      "fa": "جوزا",   "tr": "İkizler"},
    "Рак":       {"en": "Cancer",      "fa": "سرطان",  "tr": "Yengeç"},
    "Лев":       {"en": "Leo",         "fa": "اسد",    "tr": "Aslan"},
    "Дева":      {"en": "Virgo",       "fa": "سنبله",  "tr": "Başak"},
    "Весы":      {"en": "Libra",       "fa": "میزان",  "tr": "Terazi"},
    "Скорпион":  {"en": "Scorpio",     "fa": "عقرب",   "tr": "Akrep"},
    "Стрелец":   {"en": "Sagittarius", "fa": "قوس",    "tr": "Yay"},
    "Козерог":   {"en": "Capricorn",   "fa": "جدی",    "tr": "Oğlak"},
    "Водолей":   {"en": "Aquarius",    "fa": "دلو",    "tr": "Kova"},
    "Рыбы":      {"en": "Pisces",      "fa": "حوت",    "tr": "Balık"},
}


def _zodiac_name_i18n(ru_name: str, lang: str) -> str:
    """Return zodiac name in the requested language, falling back to Russian."""
    if lang == "ru":
        return ru_name
    return _ZODIAC_NAMES.get(ru_name, {}).get(lang, ru_name)


def _time_until_midnight_msk(lang: str = "ru") -> str:
    """Время до полуночи по московскому времени."""
    now_msk = datetime.now(_MSK)
    midnight_msk = (now_msk + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = midnight_msk - now_msk
    hours = int(delta.total_seconds()) // 3600
    minutes = (int(delta.total_seconds()) % 3600) // 60
    if lang == "en":
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    if lang == "fa":
        return f"{hours} ساعت {minutes} دقیقه" if hours > 0 else f"{minutes} دقیقه"
    if lang == "tr":
        return f"{hours} sa {minutes} dk" if hours > 0 else f"{minutes} dk"
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


def _after_horoscope_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    _home  = {"ru": "🏠 На Главную",  "en": "🏠 Main Menu",   "fa": "🏠 منوی اصلی",   "tr": "🏠 Ana Menü"}.get(lang, "🏠 Main Menu")
    _tarot = {"ru": "🃏 Карта Дня",   "en": "🃏 Card of Day", "fa": "🃏 کارت روز",     "tr": "🃏 Günün Kartı"}.get(lang, "🃏 Card of Day")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_home,  callback_data="menu:main")],
        [InlineKeyboardButton(text=_tarot, callback_data="menu:tarot")],
    ])


@router.callback_query(F.data == "menu:horoscope")
async def horoscope_menu(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    today_str = date.today().strftime("%Y-%m-%d")
    cache_key = make_cache_key("horoscope", user.id, today_str)

    _title       = {"ru": "Гороскоп дня",          "en": "Daily Horoscope",    "fa": "طالع‌بینی روز",    "tr": "Günlük Burç"}.get(lang, "Daily Horoscope")
    _history     = {"ru": "📋 История",             "en": "📋 History",         "fa": "📋 تاریخچه",        "tr": "📋 Geçmiş"}.get(lang, "📋 History")
    _main_menu   = {"ru": "◀️ Главное меню",        "en": "◀️ Main menu",       "fa": "◀️ منوی اصلی",     "tr": "◀️ Ana menü"}.get(lang, "◀️ Main menu")
    _enter_dob   = {"ru": "✨ Ввести дату рождения", "en": "✨ Enter birth date", "fa": "✨ تاریخ تولد",    "tr": "✨ Doğum tarihi gir"}.get(lang, "✨ Enter birth date")
    _back        = {"ru": "◀️ Назад",               "en": "◀️ Back",            "fa": "◀️ بازگشت",        "tr": "◀️ Geri"}.get(lang, "◀️ Back")
    _friend      = {"ru": "друг",                  "en": "friend",             "fa": "دوست",              "tr": "dostum"}.get(lang, "friend")

    # ── Уже получал сегодня → показываем таймер ──────────────────────────────
    already_today = await get_cached(cache_key)
    if already_today:
        time_left = _time_until_midnight_msk(lang)
        _already = {
            "ru": (f"🔯 *Гороскоп дня уже получен* — найди его выше в переписке ☝️\n\n"
                   f"Следующий гороскоп откроется через *{time_left}* 🌙\n\n"
                   f"_Каждый день — новое послание звёзд_"),
            "en": (f"🔯 *Daily horoscope already received* — find it above in the chat ☝️\n\n"
                   f"Next horoscope opens in *{time_left}* 🌙\n\n"
                   f"_Every day — a new message from the stars_"),
            "fa": (f"🔯 *طالع‌بینی روز دریافت شد* — آن را بالاتر در چت پیدا کنید ☝️\n\n"
                   f"طالع‌بینی بعدی در *{time_left}* باز می‌شود 🌙\n\n"
                   f"_هر روز — پیامی جدید از ستاره‌ها_"),
            "tr": (f"🔯 *Günlük burç alındı* — sohbetin yukarısında bulabilirsiniz ☝️\n\n"
                   f"Sonraki burç *{time_left}* içinde açılır 🌙\n\n"
                   f"_Her gün — yıldızlardan yeni bir mesaj_"),
        }.get(lang, f"🔯 *Daily horoscope already received* ☝️\n\nNext opens in *{time_left}* 🌙")
        await callback.message.edit_text(
            _already,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_history, callback_data="reports:menu")],
                [InlineKeyboardButton(text=_main_menu, callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # ── Нет даты рождения ─────────────────────────────────────────────────────
    if not user.birth_date:
        _no_dob = {
            "ru": "✨ Для гороскопа нам нужна ваша дата рождения.",
            "en": "✨ We need your date of birth for the horoscope.",
            "fa": "✨ برای طالع‌بینی به تاریخ تولد شما نیاز داریم.",
            "tr": "✨ Burç için doğum tarihinize ihtiyacımız var.",
        }.get(lang, "✨ We need your date of birth for the horoscope.")
        await callback.message.edit_text(
            _no_dob,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_enter_dob, callback_data="birth_date:collect:menu:horoscope")],
                [InlineKeyboardButton(text=_back, callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # ── Этап 1: «Считываю вашу дату» ─────────────────────────────────────────
    _reading_date = {
        "ru": "🌙 _Считываю вашу дату..._",
        "en": "🌙 _Reading your date..._",
        "fa": "🌙 _تاریخ شما را می‌خوانم..._",
        "tr": "🌙 _Tarihinizi okuyorum..._",
    }.get(lang, "🌙 _Reading your date..._")
    await callback.message.edit_text(_reading_date, parse_mode="Markdown")
    await callback.answer()
    await asyncio.sleep(3)

    # ── Этап 2: «Считываю ваш знак зодиака» ──────────────────────────────────
    birth = parse_birth_date(user.birth_date)
    if not birth:
        _err = {"ru": "❌ Дата рождения не распознана.", "en": "❌ Birth date not recognized.",
                "fa": "❌ تاریخ تولد شناسایی نشد.", "tr": "❌ Doğum tarihi tanınamadı."}.get(lang, "❌ Birth date not recognized.")
        await callback.message.edit_text(_err)
        return

    zodiac_emoji, zodiac_name_ru = get_zodiac(birth.day, birth.month)
    zodiac_name = _zodiac_name_i18n(zodiac_name_ru, lang)
    _reading_sign = {
        "ru": f"🔮 _Считываю ваш знак зодиака..._\n\n_{zodiac_emoji} {zodiac_name}_",
        "en": f"🔮 _Reading your zodiac sign..._\n\n_{zodiac_emoji} {zodiac_name}_",
        "fa": f"🔮 _علامت زودیاک شما را می‌خوانم..._\n\n_{zodiac_emoji} {zodiac_name}_",
        "tr": f"🔮 _Zodyak işaretinizi okuyorum..._\n\n_{zodiac_emoji} {zodiac_name}_",
    }.get(lang, f"🔮 _Reading your zodiac sign..._\n\n_{zodiac_emoji} {zodiac_name}_")
    await callback.message.edit_text(_reading_sign, parse_mode="Markdown")
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
        title=f"{_title} — {zodiac_emoji} {zodiac_name} | {date.today().strftime('%d.%m.%Y')}",
        content=horoscope_text,
        metadata={"zodiac": zodiac_name_ru, "zodiac_emoji": zodiac_emoji, "date": today_str},
    )

    # ── Финальное сообщение ───────────────────────────────────────────────────
    name = user.first_name or _friend
    text = (
        f"🔯 *{_title} — {name}*\n"
        f"_{zodiac_emoji} {zodiac_name} | {date.today().strftime('%d.%m.%Y')}_\n\n"
        f"{horoscope_text}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=_after_horoscope_keyboard(lang),
        parse_mode="Markdown",
    )
