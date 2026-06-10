"""Карта дня — расклад на один Старший Аркан."""
import json
import random
from pathlib import Path
from datetime import date, datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.services.numerology import calculate_all
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.services.thinking import random_thinking
from bot.prompts.prompts import TAROT_CARD_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import after_tarot_keyboard, limit_reached_keyboard, back_to_main
from bot.utils import parse_birth_date

router = Router()

# ─── Карты Старших Арканов ────────────────────────────────────────────────────

MAJOR_ARCANA = [
    ("00_fool",            "Шут",                "0 — Шут"),
    ("01_magician",        "Маг",                "I — Маг"),
    ("02_high_priestess",  "Верховная Жрица",    "II — Верховная Жрица"),
    ("03_empress",         "Императрица",         "III — Императрица"),
    ("04_emperor",         "Император",           "IV — Император"),
    ("05_hierophant",      "Иерофант",            "V — Иерофант"),
    ("06_lovers",          "Влюблённые",          "VI — Влюблённые"),
    ("07_chariot",         "Колесница",           "VII — Колесница"),
    ("08_strength",        "Сила",               "VIII — Сила"),
    ("09_hermit",          "Отшельник",           "IX — Отшельник"),
    ("10_wheel_of_fortune","Колесо Фортуны",      "X — Колесо Фортуны"),
    ("11_justice",         "Справедливость",      "XI — Справедливость"),
    ("12_hanged_man",      "Повешенный",          "XII — Повешенный"),
    ("13_death",           "Смерть",             "XIII — Смерть"),
    ("14_temperance",      "Умеренность",         "XIV — Умеренность"),
    ("15_devil",           "Дьявол",             "XV — Дьявол"),
    ("16_tower",           "Башня",              "XVI — Башня"),
    ("17_star",            "Звезда",             "XVII — Звезда"),
    ("18_moon",            "Луна",               "XVIII — Луна"),
    ("19_sun",             "Солнце",             "XIX — Солнце"),
    ("20_judgement",       "Суд",                "XX — Суд"),
    ("21_world",           "Мир",                "XXI — Мир"),
]

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "tarot"

# Московское время UTC+3
_MSK = timezone(timedelta(hours=3))


def _pick_card_for_today(user_id: int) -> tuple[str, str, str]:
    """Детерминированно выбрать карту на сегодня для пользователя."""
    today = date.today()
    seed = user_id * 1000 + today.toordinal()
    rng = random.Random(seed)
    return rng.choice(MAJOR_ARCANA)


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


# ─── Обработчики ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:tarot")
async def tarot_menu(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    today_str = date.today().strftime("%Y-%m-%d")
    cache_key = make_cache_key("tarot_card", user.id, today_str)

    # ── Уже получал сегодня → показываем таймер ──────────────────────────────
    already_today = await get_cached(cache_key)
    if already_today:
        time_left = _time_until_midnight_msk()
        _already = {
            "ru": f"🃏 *Карта дня уже получена* — найди её выше в переписке ☝️\n\nСледующая карта откроется через *{time_left}* 🌙\n\n_Каждый день — новое послание Вселенной_",
            "en": f"🃏 *Card of the day already received* — find it above in the chat ☝️\n\nNext card opens in *{time_left}* 🌙\n\n_Every day — a new message from the Universe_",
            "fa": f"🃏 *کارت روز دریافت شد* — آن را بالاتر در چت پیدا کنید ☝️\n\nکارت بعدی در *{time_left}* باز می‌شود 🌙\n\n_هر روز — پیامی جدید از کیهان_",
            "tr": f"🃏 *Günün kartı alındı* — sohbetin yukarısında bulabilirsiniz ☝️\n\nSonraki kart *{time_left}* içinde açılır 🌙\n\n_Her gün — evrenden yeni bir mesaj_",
        }.get(lang, f"🃏 *Card of the day already received* ☝️\n\nNext opens in *{time_left}* 🌙")
        await callback.message.edit_text(_already, reply_markup=back_to_main(), parse_mode="Markdown")
        await callback.answer()
        return

    # ── Проверка лимита за период ─────────────────────────────────────────────
    has_limit, used, max_val = await check_limit(session, user.id, "tarot_cards")
    if not has_limit:
        _limit_text = {
            "ru": "🔒 *Карта дня*\n\nЛимит карт за этот период исчерпан.\n\n• Бесплатно: 2 карты за период\n• Lite: 5 карт за период\n• Premium: 10 карт за период\n• Pro: 30 карт за период",
            "en": "🔒 *Card of the Day*\n\nCard limit for this period is reached.\n\n• Free: 2 cards per period\n• Lite: 5 cards per period\n• Premium: 10 cards per period\n• Pro: 30 cards per period",
            "fa": "🔒 *کارت روز*\n\nمحدودیت کارت برای این دوره تمام شد.\n\n• رایگان: ۲ کارت\n• Lite: ۵ کارت\n• Premium: ۱۰ کارت\n• Pro: ۳۰ کارت",
            "tr": "🔒 *Günün Kartı*\n\nBu dönem için kart limiti doldu.\n\n• Ücretsiz: 2 kart\n• Lite: 5 kart\n• Premium: 10 kart\n• Pro: 30 kart",
        }.get(lang, "🔒 *Card of the Day*\n\nCard limit reached.")
        await callback.message.edit_text(_limit_text, reply_markup=limit_reached_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    # ── Нет даты рождения ─────────────────────────────────────────────────────
    if not user.birth_date:
        _no_dob = {
            "ru": "✨ Для карты дня нам нужна ваша дата рождения.",
            "en": "✨ We need your birth date for the card of the day.",
            "fa": "✨ برای کارت روز به تاریخ تولد شما نیاز داریم.",
            "tr": "✨ Günün kartı için doğum tarihinize ihtiyacımız var.",
        }.get(lang, "✨ We need your birth date for the card of the day.")
        _enter = {"ru": "✨ Ввести дату рождения", "en": "✨ Enter birth date",
                  "fa": "✨ تاریخ تولد را وارد کنید", "tr": "✨ Doğum tarihi gir"}.get(lang, "✨ Enter birth date")
        _back = {"ru": "◀️ Назад", "en": "◀️ Back", "fa": "◀️ بازگشت", "tr": "◀️ Geri"}.get(lang, "◀️ Back")
        await callback.message.edit_text(
            _no_dob,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_enter, callback_data="birth_date:collect:menu:tarot")],
                [InlineKeyboardButton(text=_back, callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # ── Генерируем карту ──────────────────────────────────────────────────────
    thinking_msg = await callback.message.edit_text(random_thinking())

    file_key, card_name_ru, card_label = _pick_card_for_today(user.id)

    birth_date_obj = parse_birth_date(user.birth_date)
    if not birth_date_obj:
        _err = {"ru": "❌ Дата рождения не найдена.", "en": "❌ Birth date not found.",
                "fa": "❌ تاریخ تولد یافت نشد.", "tr": "❌ Doğum tarihi bulunamadı."}.get(lang, "❌ Birth date not found.")
        await thinking_msg.edit_text(_err)
        await callback.answer()
        return

    nums = calculate_all(birth_date_obj)
    _friend_name = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    context = {
        "name": user.first_name or _friend_name,
        "birth_date": user.birth_date,
        "card": card_label,
        "card_name": card_name_ru,
        "numbers": nums,
        "date": today_str,
    }
    user_msg = (
        f"Дай интерпретацию карты дня «{card_label}».\n"
        f"Данные: {json.dumps(context, ensure_ascii=False)}"
    )
    card_text = await generate(
        session, user.id, "tarot_card",
        TAROT_CARD_PROMPT(lang), user_msg,
        complexity="medium", max_tokens=500,
    )

    # Сохраняем в кэш (до полуночи МСК)
    now_msk = datetime.now(_MSK)
    midnight_msk = (now_msk + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    ttl = int((midnight_msk - now_msk).total_seconds())
    await set_cached(cache_key, card_text, ttl=ttl)

    # Сохраняем в историю
    from bot.services.reports_service import save_report
    _save_title = {"ru": "Карта дня", "en": "Card of the Day", "fa": "کارت روز", "tr": "Günün Kartı"}.get(lang, "Card of the Day")
    await save_report(
        session, user.id, "tarot_card",
        title=f"{_save_title} — {card_label} | {date.today().strftime('%d.%m.%Y')}",
        content=card_text,
        metadata={"card_key": file_key, "card_name": card_name_ru, "date": today_str},
    )
    await consume_limit(session, user.id, "tarot_cards")
    await consume_limit(session, user.id, "ai_messages")

    # ── Отправляем: фото сверху, текст+кнопки снизу ───────────────────────────
    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _card_title = {"ru": "Карта дня", "en": "Card of the day", "fa": "کارت روز", "tr": "Günün kartı"}.get(lang, "Card of the day")
    text = f"🃏 *{_card_title} — {name}*\n_{date.today().strftime('%d.%m.%Y')}_\n\n{card_text}"

    image_path = ASSETS_DIR / f"{file_key}.png"
    try:
        await thinking_msg.delete()
    except Exception:
        pass

    if image_path.exists():
        try:
            await callback.message.answer_photo(photo=FSInputFile(str(image_path)))
        except Exception:
            pass

    await callback.message.answer(text, reply_markup=after_tarot_keyboard(), parse_mode="Markdown")
    await callback.answer()
