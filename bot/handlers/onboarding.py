"""Onboarding flow — показывается один раз для новых пользователей."""
import asyncio
import logging
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import User, UserProfile
from bot.i18n.translations import t

router = Router()
logger = logging.getLogger(__name__)


class OnboardingFSM(StatesGroup):
    waiting_birth_date = State()


# ─── Проверка / отметка онбординга ────────────────────────────────────────────

async def is_onboarding_done(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return False
    prefs = profile.preferences or {}
    return bool(prefs.get("onboarding_done"))


async def mark_onboarding_done(session: AsyncSession, user_id: int, interest: str | None = None):
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile:
        prefs = dict(profile.preferences or {})
        prefs["onboarding_done"] = True
        if interest:
            prefs["onboarding_interest"] = interest
        profile.preferences = prefs
        await session.commit()


# ─── Клавиатуры онбординга ────────────────────────────────────────────────────

def _screen1_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("ob_btn_continue", lang), callback_data="ob:2")]
    ])


def _screen2_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("ob_btn_love", lang),     callback_data="ob:3:love")],
        [InlineKeyboardButton(text=t("ob_btn_forecast", lang), callback_data="ob:3:forecast")],
        [InlineKeyboardButton(text=t("ob_btn_self", lang),     callback_data="ob:3:self")],
    ])


def _screen3_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("ob_btn_learn_more", lang), callback_data="ob:4")]
    ])


def _screen4_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("ob_btn_love", lang),     callback_data="ob:5:love")],
        [InlineKeyboardButton(text=t("ob_btn_money", lang),    callback_data="ob:5:money")],
        [InlineKeyboardButton(text=t("ob_btn_future", lang),   callback_data="ob:5:future")],
        [InlineKeyboardButton(text=t("ob_btn_self", lang),     callback_data="ob:5:self")],
    ])


def _screen_trial_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("menu_daily", lang),      callback_data="menu:daily")],
        [InlineKeyboardButton(text=t("menu_reading", lang),    callback_data="free:start")],
        [InlineKeyboardButton(text=t("ob_btn_open_menu", lang), callback_data="ob:open_menu")],
    ])


# ─── Запуск онбординга ────────────────────────────────────────────────────────

async def start_onboarding(message, user: User, lang: str = "ru"):
    """Запустить онбординг — показать первый экран."""
    await message.answer(
        t("ob_screen1", lang),
        reply_markup=_screen1_kb(lang),
        parse_mode="Markdown",
    )


# ─── Обработчики экранов ──────────────────────────────────────────────────────

@router.callback_query(F.data == "ob:2")
async def ob_screen2(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    """Шаг 2 — запрос даты рождения."""
    await callback.message.edit_text(
        t("ob_screen2", lang),
        parse_mode="Markdown",
    )
    await state.set_state(OnboardingFSM.waiting_birth_date)
    # Сохраняем lang в FSM чтобы использовать при получении даты
    await state.update_data(lang=lang)
    await callback.answer()


@router.message(OnboardingFSM.waiting_birth_date, ~F.text.startswith("/"))
async def ob_receive_birth_date(message: Message, user: User, state: FSMContext, session: AsyncSession):
    """Получаем дату рождения, проверяем, продолжаем онбординг."""
    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", "ru")

    text = (message.text or "").strip()

    dt = None
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    if dt is None:
        await message.answer(t("ob_date_invalid", lang), parse_mode="Markdown")
        return

    age = (date.today() - dt).days // 365

    if age > 100 or dt > date.today():
        await message.answer(t("ob_date_invalid_range", lang), parse_mode="Markdown")
        return

    # Сохраняем дату рождения
    user.birth_date = dt.strftime("%d.%m.%Y")
    await session.commit()

    await state.clear()
    # Восстанавливаем lang после clear (он потерялся вместе с FSM)
    # lang уже получен выше из fsm_data — используем его дальше

    # Продолжаем онбординг — выбор темы
    await message.answer(
        t("ob_screen3_intro", lang),
        reply_markup=_screen2_kb(lang),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("ob:3:"))
async def ob_screen3(callback: CallbackQuery, lang: str = "ru"):
    interest = callback.data.split(":")[-1]
    # Выбираем ключ перевода по теме
    key_map = {
        "love":     "ob_screen3_love",
        "forecast": "ob_screen3_forecast",
        "self":     "ob_screen3_self",
    }
    key = key_map.get(interest, "ob_screen3_self")
    text = t(key, lang)
    await callback.message.edit_text(text, reply_markup=_screen3_kb(lang), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "ob:4")
async def ob_screen4(callback: CallbackQuery, lang: str = "ru"):
    await callback.message.edit_text(
        t("ob_screen4", lang),
        reply_markup=_screen4_kb(lang),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ob:5:"))
async def ob_screen5_animation(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    interest = callback.data.split(":")[-1]

    # Анимация ожидания
    try:
        await callback.message.edit_text(t("ob_anim_1", lang))
        await asyncio.sleep(1.5)
        await callback.message.edit_text(t("ob_anim_2", lang))
        await asyncio.sleep(1.5)
        await callback.message.edit_text(t("ob_anim_3", lang))
        await asyncio.sleep(1.5)
    except Exception as e:
        logger.warning("Onboarding animation error: %s", e)

    await mark_onboarding_done(session, user.id, interest)

    # Проверяем спонсорскую плашку
    from bot.handlers.sponsor import get_sponsor_state, show_sponsor_screen
    sponsor = await get_sponsor_state()

    if sponsor["enabled"] and sponsor["link"]:
        await show_sponsor_screen(callback, callback.message.bot, sponsor["link"])
        from bot.utils import ensure_keyboard
        await ensure_keyboard(callback.message, user.telegram_id, lang)
        return

    # Открываем главное меню
    from bot.keyboards.main import main_menu
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import set_menu_msg_id
    from bot.utils import ensure_keyboard

    name = user.first_name or None
    await callback.message.edit_text(
        _welcome_text(name, lang),
        reply_markup=main_menu(lang),
        parse_mode="Markdown",
    )
    await set_menu_msg_id(user.telegram_id, callback.message.message_id)
    await ensure_keyboard(callback.message, user.telegram_id, lang)
    await callback.answer()


@router.callback_query(F.data == "ob:open_menu")
async def ob_open_menu(callback: CallbackQuery, user: User, lang: str = "ru"):
    """Завершить онбординг → главное меню."""
    from bot.keyboards.main import main_menu
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import set_menu_msg_id
    from bot.utils import ensure_keyboard

    name = user.first_name or None

    await callback.message.edit_text(
        _welcome_text(name, lang),
        reply_markup=main_menu(lang),
        parse_mode="Markdown",
    )
    await set_menu_msg_id(user.telegram_id, callback.message.message_id)
    await ensure_keyboard(callback.message, user.telegram_id, lang)
    await callback.answer()
