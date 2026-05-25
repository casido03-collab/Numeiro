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
from bot.prompts.prompts import FREE_BIRTH_REPORT_PROMPT, FULL_MATRIX_PROMPT, UPSELL_PROMPT
from bot.keyboards.main import sphere_menu, upsell_keyboard, limit_reached_keyboard, back_to_main, main_menu, upsell_keyboard_reading, after_reading_keyboard_matrix
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai
from bot.services.thinking import random_thinking

router = Router()

SPHERE_NAMES = {
    "love": "любовь и отношения",
    "money": "деньги и финансы",
    "work": "работа и карьера",
    "health": "здоровье и энергия",
    "family": "семья",
    "decision": "важные решения",
    "general": "общий прогноз",
}


async def show_sphere_selection(msg: Message, user: User):
    name = user.first_name or "друг"
    await msg.edit_text(
        f"🔮 *{name}*, выберите сферу для разбора:",
        reply_markup=sphere_menu("sphere", back="menu:main"),
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "menu:reading")
async def menu_reading(callback: CallbackQuery, user: User, session: AsyncSession):
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

    await show_sphere_selection(callback.message, user)
    await callback.answer()


@router.callback_query(F.data.startswith("sphere:"))
async def select_sphere(callback: CallbackQuery, user: User, session: AsyncSession):
    sphere = callback.data.split(":")[-1]

    has_limit, used, max_val = await check_limit(session, user.id, "mini_readings")
    if not has_limit:
        await callback.message.edit_text(
            "✨ Ваш лимит исчерпан\n\nОткройте больше возможностей для продолжения:",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    import random
    thinking_msg = await callback.message.edit_text(random_thinking())

    birth_date = parse_birth_date(user.birth_date)
    if not birth_date:
        await thinking_msg.edit_text("❌ Ошибка: дата рождения не найдена.")
        await callback.answer()
        return

    # Кэш
    cache_key = make_cache_key("free_reading", user.birth_date, sphere)
    cached = await get_cached(cache_key)

    if not cached:
        nums = numerology.calculate_all(birth_date)
        traits = numerology.get_traits(nums["life_path"])
        context = {
            "name": user.first_name or "друг",
            "birth_date": user.birth_date,
            "sphere": SPHERE_NAMES.get(sphere, sphere),
            "numbers": nums,
            "traits": traits,
        }
        user_msg = f"Сделай бесплатный разбор для сферы '{SPHERE_NAMES.get(sphere, sphere)}'.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(session, user.id, "free_reading", FREE_BIRTH_REPORT_PROMPT, user_msg, complexity="simple", max_tokens=400)
        await set_cached(cache_key, cached, ttl=3600 * 24 * 3)

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "mini_report",
        title=f"Разбор: {SPHERE_NAMES.get(sphere, sphere)}",
        content=cached,
        metadata={"sphere": sphere, "birth_date": user.birth_date},
    )
    await consume_limit(session, user.id, "mini_readings")
    await consume_limit(session, user.id, "ai_messages")

    name = user.first_name or "друг"
    text = f"🔮 *Разбор для {name}*\n\n{cached}"

    # CTA кнопка встроена прямо в клавиатуру — не нужен лишний API-вызов
    from bot.keyboards.main import upsell_keyboard_reading
    await safe_edit_ai(thinking_msg, text, reply_markup=upsell_keyboard_reading())
    await callback.answer()


@router.callback_query(F.data == "matrix:start")
async def matrix_start(callback: CallbackQuery, user: User, session: AsyncSession):
    if not user.birth_date:
        await callback.message.edit_text(
            "✨ Введи свою дату рождения через *«Мой разбор»*:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    has_limit, used, max_val = await check_limit(session, user.id, "mini_readings")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Полная матрица судьбы*\n\nЭта функция требует подписки или разовой покупки.",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    import random
    thinking_msg = await callback.message.edit_text(random_thinking())

    birth_date = parse_birth_date(user.birth_date)
    cache_key = make_cache_key("full_matrix", user.birth_date)
    cached = await get_cached(cache_key)

    if not cached:
        mat = matrix_svc.calculate_matrix(birth_date)
        ctx = matrix_svc.matrix_to_context(mat)
        nums = numerology.calculate_all(birth_date)
        context = {
            "name": user.first_name or "друг",
            "birth_date": user.birth_date,
            "matrix": ctx,
            "numbers": nums,
        }
        user_msg = f"Сделай полный разбор матрицы судьбы.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(session, user.id, "full_matrix", FULL_MATRIX_PROMPT, user_msg, complexity="complex", max_tokens=900)
        await set_cached(cache_key, cached, ttl=3600 * 24 * 7)

    from bot.services.reports_service import save_report as _save
    await _save(
        session, user.id, "destiny_matrix",
        title="Матрица судьбы",
        content=cached,
        metadata={"birth_date": user.birth_date},
    )
    await consume_limit(session, user.id, "mini_readings")
    await consume_limit(session, user.id, "ai_messages")

    name = user.first_name or "друг"
    text = f"🌟 *Матрица судьбы — {name}*\n\n{cached}"
    await safe_edit_ai(thinking_msg, text, reply_markup=after_reading_keyboard_matrix())
    await callback.answer()


async def show_free_reading(msg: Message, user: User, session):
    await show_sphere_selection(msg, user)
