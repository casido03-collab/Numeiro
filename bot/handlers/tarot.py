"""Карта дня — расклад на один Старший Аркан."""
import json
import random
from pathlib import Path
from datetime import date
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.services.numerology import calculate_all
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.services.thinking import random_thinking
from bot.prompts.prompts import TAROT_CARD_PROMPT
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


def _pick_card_for_today(user_id: int) -> tuple[str, str, str]:
    """Детерминированно выбрать карту на сегодня для пользователя."""
    today = date.today()
    seed = user_id * 1000 + today.toordinal()
    rng = random.Random(seed)
    return rng.choice(MAJOR_ARCANA)


# ─── Обработчики ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:tarot")
async def tarot_menu(callback: CallbackQuery, user: User, session: AsyncSession):
    has_limit, used, max_val = await check_limit(session, user.id, "tarot_cards")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Карта дня*\n\nЭта функция требует подписки или доступных лимитов.\n\n"
            "• Бесплатно: 2 карты за период\n"
            "• Lite: 5 карт за период\n"
            "• Premium: 10 карт за период\n"
            "• Pro: 30 карт за период",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            "✨ Для карты дня нам нужна ваша дата рождения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # Показываем загрузочную фразу
    thinking_msg = await callback.message.edit_text(random_thinking())

    file_key, card_name_ru, card_label = _pick_card_for_today(user.id)
    today_str = date.today().strftime("%Y-%m-%d")

    birth_date_obj = parse_birth_date(user.birth_date)
    if not birth_date_obj:
        await thinking_msg.edit_text("❌ Дата рождения не найдена.")
        await callback.answer()
        return

    # Проверяем кэш (карта одна на день для пользователя)
    cache_key = make_cache_key("tarot_card", user.id, today_str)
    cached_text = await get_cached(cache_key)

    if not cached_text:
        nums = calculate_all(birth_date_obj)
        context = {
            "name": user.first_name or "друг",
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
        cached_text = await generate(
            session, user.id, "tarot_card",
            TAROT_CARD_PROMPT, user_msg,
            complexity="medium", max_tokens=500,
        )
        await set_cached(cache_key, cached_text, ttl=3600 * 20)  # до конца дня

    # Сохраняем в историю
    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "tarot_card",
        title=f"Карта дня — {card_label} | {date.today().strftime('%d.%m.%Y')}",
        content=cached_text,
        metadata={"card_key": file_key, "card_name": card_name_ru, "date": today_str},
    )
    await consume_limit(session, user.id, "tarot_cards")
    await consume_limit(session, user.id, "ai_messages")

    # Отправляем фото отдельным сообщением (визуал), текст+кнопки — редактируем thinking_msg
    image_path = ASSETS_DIR / f"{file_key}.png"
    if image_path.exists():
        try:
            await callback.message.answer_photo(photo=FSInputFile(str(image_path)))
        except Exception:
            pass  # не критично — текст придёт в любом случае

    name = user.first_name or "друг"
    text = f"🃏 *Карта дня — {name}*\n_{date.today().strftime('%d.%m.%Y')}_\n\n{cached_text}"
    from bot.utils import safe_edit_ai
    await safe_edit_ai(thinking_msg, text, reply_markup=after_tarot_keyboard())

    await callback.answer()
