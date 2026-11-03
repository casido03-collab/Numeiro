from bot.services.catalog import product_offer
from bot.services.limits import has_credit as product_has_credit
"""Бесплатный разбор + матрица судьбы."""
import json
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services import numerology, matrix as matrix_svc
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.prompts.prompts import PAID_MINI_REPORT_PROMPT, FULL_MATRIX_PROMPT, UPSELL_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import sphere_menu, upsell_keyboard, limit_reached_keyboard, back_to_main, main_menu, upsell_keyboard_reading, after_reading_keyboard_matrix
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai
from bot.services.thinking import random_thinking

router = Router()

# Русские названия — используются только как фоллбэк для кэш-ключей
SPHERE_NAMES = {
    "love": "любовь и отношения", "money": "деньги и финансы", "work": "работа и карьера",
    "health": "здоровье и энергия", "family": "семья", "decision": "важные решения",
    "general": "общий прогноз", "purpose": "предназначение и миссия", "growth": "личностный рост",
    "partnership": "партнёрство и отношения", "children": "дети и родительство",
    "education": "образование и обучение", "relocation": "переезд и путешествия",
    "home": "жильё и дом", "spiritual": "духовное развитие", "creativity": "творчество и таланты",
    "friendship": "дружба и окружение", "motivation": "мотивация и энергия",
    "inner_peace": "внутренний мир и покой", "karma": "карма и прошлое", "career": "карьерный рост",
}


def _sphere(sphere: str, lang: str = "ru") -> str:
    """Название сферы на языке пользователя."""
    translated = t(f"sphere_{sphere}", lang)
    # t() возвращает ключ если не найдено — фоллбэк на SPHERE_NAMES
    if translated == f"sphere_{sphere}":
        return SPHERE_NAMES.get(sphere, sphere)
    return translated


async def show_sphere_selection(msg: Message, user: User, lang: str = "ru"):
    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _prompt = {"ru": "выберите сферу для разбора", "en": "choose a sphere for your reading",
               "fa": "حوزه‌ای را برای بررسی انتخاب کنید", "tr": "okuma için bir alan seçin"}.get(lang, "choose a sphere")
    await msg.edit_text(
        f"🔮 *{name}*, {_prompt}:",
        reply_markup=sphere_menu("sphere", back="menu:main"),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "menu:reading")
async def menu_reading(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    if not user.birth_date:
        # Запустим FSM для ввода даты
        from bot.keyboards.main import cancel_fsm_keyboard
        from aiogram.fsm.context import FSMContext
        from bot.handlers.profile import ProfileFSM
        state: FSMContext = callback.data  # получим ниже через middleware
        # Упрощённо: просим ввести дату текстом и переходим к FSM через кнопку
        await callback.message.edit_text(
            "✨ Для разбора нам нужна ваша дата рождения.\n\nНажми *«Ввести дату рождения»* чтобы начать ввод:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await show_sphere_selection(callback.message, user, lang)  # reading оставляем как есть
    await callback.answer()


@router.callback_query(F.data.startswith("sphere:"))
async def select_sphere(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    sphere = callback.data.split(":")[-1]

    from bot.services.limits import has_credit, is_vip, check_vip_limit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    _is_vip = await is_vip(user.id)
    if not _is_vip and not await has_credit(user.id, "mini_reading"):
        _locked = product_offer("mini_reading", lang)
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("mini_reading", 49, 49, lang), parse_mode="Markdown")
        await callback.answer()
        return

    if _is_vip and not await check_vip_limit(user.id, "mini_reading") and not await product_has_credit(user.id, "mini_reading"):
        _exhausted = {
            "ru": "💎 Лимит VIP по этому разделу исчерпан на этот месяц.",
            "en": "💎 VIP limit for this section exhausted this month.",
            "fa": "💎 محدودیت VIP برای این بخش تمام شده.",
            "tr": "💎 Bu bölüm için VIP limitiniz doldu.",
        }.get(lang, "💎 VIP limit exhausted.")
        await callback.message.edit_text(_exhausted, reply_markup=back_to_main(), parse_mode="Markdown")
        await callback.answer()
        return

    import random
    thinking_msg = await callback.message.edit_text(random_thinking())

    birth_date = parse_birth_date(user.birth_date)
    if not birth_date:
        await thinking_msg.edit_text("❌ Ошибка: дата рождения не найдена.")
        await callback.answer()
        return

    from bot.services.fulfillment import generate_paid_report
    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    sphere_label = _sphere(sphere, lang)
    nums = numerology.calculate_all(birth_date)
    context = {"name": user.first_name or _friend, "birth_date": user.birth_date,
               "sphere": sphere_label, "numbers": nums, "traits": numerology.get_traits(nums["life_path"])}
    report = await generate_paid_report(
        session, user.id, "mini_reading", "mini_report", f"Разбор: {SPHERE_NAMES.get(sphere, sphere)}",
        context, PAID_MINI_REPORT_PROMPT(lang), lang, max_tokens=2000,
        metadata={"sphere": sphere, "birth_date": user.birth_date})
    cached = report.content

    name = user.first_name or _friend
    _title = {"ru": "Разбор для", "en": "Reading for", "fa": "بررسی برای", "tr": "Okuma:"}.get(lang, "Reading for")
    text = f"🔮 {_title} {name}\n\n{cached}"

    # CTA кнопка встроена прямо в клавиатуру — не нужен лишний API-вызов
    from bot.keyboards.main import upsell_keyboard_reading
    await safe_edit_ai(thinking_msg, text, reply_markup=upsell_keyboard_reading())
    await callback.answer()


@router.callback_query(F.data == "matrix:start")
async def matrix_start(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.services.limits import has_credit as _has_credit_matrix, is_vip as _is_vip_matrix, check_vip_limit as _check_vip_matrix
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    _vip_active = await _is_vip_matrix(user.id)
    if not _vip_active and not await _has_credit_matrix(user.id, "full_matrix"):
        _locked = product_offer("full_matrix", lang)
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("full_matrix", 199, 199, lang), parse_mode="Markdown")
        await callback.answer()
        return

    if _vip_active and not await _check_vip_matrix(user.id, "full_matrix") and not await product_has_credit(user.id, "full_matrix"):
        _exhausted = {
            "ru": "💎 Лимит VIP по этому разделу исчерпан на этот месяц.",
            "en": "💎 VIP limit for this section exhausted this month.",
            "fa": "💎 محدودیت VIP برای این بخش تمام شده.",
            "tr": "💎 Bu bölüm için VIP limitiniz doldu.",
        }.get(lang, "💎 VIP limit exhausted.")
        await callback.message.edit_text(_exhausted, reply_markup=back_to_main(), parse_mode="Markdown")
        await callback.answer()
        return

    if not user.birth_date:
        await callback.message.edit_text(
            "✨ Для матрицы судьбы нужна дата рождения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="birth_date:collect:matrix:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    import random
    thinking_msg = await callback.message.edit_text(random_thinking())

    birth_date = parse_birth_date(user.birth_date)
    from bot.services.fulfillment import generate_paid_report
    context = {"name": user.first_name or "друг", "birth_date": user.birth_date,
               "matrix": matrix_svc.matrix_to_context(matrix_svc.calculate_matrix(birth_date)),
               "numbers": numerology.calculate_all(birth_date)}
    report = await generate_paid_report(
        session, user.id, "full_matrix", "destiny_matrix", "Матрица судьбы",
        context, FULL_MATRIX_PROMPT(lang), lang, complexity="complex", max_tokens=4200,
        metadata={"birth_date": user.birth_date})
    cached = report.content

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _matrix_title = {"ru": "Матрица судьбы", "en": "Destiny Matrix", "fa": "ماتریس سرنوشت", "tr": "Kader Matrisi"}.get(lang, "Destiny Matrix")
    text = f"🌟 {_matrix_title} — {name}\n\n{cached}"
    await safe_edit_ai(thinking_msg, text, reply_markup=after_reading_keyboard_matrix())
    await callback.answer()


async def show_free_reading(msg: Message, user: User, session, lang: str = "ru"):
    await show_sphere_selection(msg, user, lang)
