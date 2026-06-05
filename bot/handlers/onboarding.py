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


# ─── Экраны онбординга ────────────────────────────────────────────────────────

def _screen1_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Продолжить", callback_data="ob:2")]
    ])


def _screen2_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Отношения", callback_data="ob:3:love")],
        [InlineKeyboardButton(text="🌙 Прогнозы", callback_data="ob:3:forecast")],
        [InlineKeyboardButton(text="🔮 Самопознание", callback_data="ob:3:self")],
    ])


def _screen3_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Узнать больше", callback_data="ob:4")]
    ])


def _screen4_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Отношения", callback_data="ob:5:love")],
        [InlineKeyboardButton(text="💰 Деньги", callback_data="ob:5:money")],
        [InlineKeyboardButton(text="🌙 Будущее", callback_data="ob:5:future")],
        [InlineKeyboardButton(text="🧠 Самопознание", callback_data="ob:5:self")],
    ])


def _screen_trial_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Энергия дня", callback_data="menu:daily")],
        [InlineKeyboardButton(text="✨ Мой разбор", callback_data="free:start")],
        [InlineKeyboardButton(text="◀️ Открыть меню", callback_data="ob:open_menu")],
    ])


SCREEN3_TEXTS = {
    "love": (
        "❤️ *Многие люди приходят сюда именно из-за отношений.*\n\n"
        "Иногда между людьми возникает необъяснимая связь.\n"
        "А иногда судьба словно специально сталкивает нас с определёнными людьми.\n\n"
        "✨ Возможно, некоторые ответы уже ждут вас."
    ),
    "forecast": (
        "🌙 *Некоторые периоды ощущаются особенно странно.*\n\n"
        "Иногда энергия словно меняется:\n"
        "меняется настроение, мысли и даже люди вокруг.\n\n"
        "Многие замечают это ещё до важных событий."
    ),
    "self": (
        "🔮 *Иногда человеку достаточно одного ответа,*\n"
        "чтобы посмотреть на свою жизнь под другим углом.\n\n"
        "Нумерология и энергетические практики помогают лучше понять:\n"
        "• свои сильные стороны\n"
        "• внутренние циклы\n"
        "• повторяющиеся события"
    ),
}


async def start_onboarding(message, user: User):
    """Запустить онбординг — показать первый экран."""
    await message.answer(
        "✨ *Иногда жизнь приводит нас сюда не случайно.*\n\n"
        "Многие замечают повторяющиеся числа, странные совпадения и внутреннее чувство,\n"
        "будто впереди что-то меняется.\n\n"
        "Возможно, именно сейчас для вас начинается новый этап.",
        reply_markup=_screen1_kb(),
        parse_mode="Markdown",
    )


# ─── Обработчики экранов ──────────────────────────────────────────────────────

@router.callback_query(F.data == "ob:2")
async def ob_screen2(callback: CallbackQuery, state: FSMContext):
    """Шаг 2 — запрос даты рождения для проверки возраста."""
    await callback.message.edit_text(
        "📅 *Для персонального разбора мне нужна ваша дата рождения.*\n\n"
        "Напишите её в формате: *ДД.ММ.ГГГГ*\n\n"
        "_Например: 15.03.1990_",
        parse_mode="Markdown",
    )
    await state.set_state(OnboardingFSM.waiting_birth_date)
    await callback.answer()


@router.message(OnboardingFSM.waiting_birth_date, ~F.text.startswith("/"))
async def ob_receive_birth_date(message: Message, user: User, state: FSMContext, session: AsyncSession):
    """Получаем дату рождения, проверяем возраст, продолжаем онбординг."""
    text = (message.text or "").strip()

    # Парсим дату
    dt = None
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue

    if dt is None:
        await message.answer(
            "❌ Не могу распознать дату. Введите в формате *ДД.ММ.ГГГГ*\n\nНапример: *15.03.1990*",
            parse_mode="Markdown",
        )
        return

    age = (date.today() - dt).days // 365

    if age < 18:
        await state.clear()
        await message.answer(
            "🔒 *Доступ ограничен*\n\n"
            "Этот бот предназначен только для пользователей старше 18 лет.",
            parse_mode="Markdown",
        )
        return

    if age > 100 or dt > date.today():
        await message.answer(
            "❌ Некорректная дата. Проверьте и введите снова.",
            parse_mode="Markdown",
        )
        return

    # Сохраняем дату рождения
    user.birth_date = dt.strftime("%d.%m.%Y")
    await session.commit()

    await state.clear()

    # Продолжаем онбординг — показываем выбор темы
    await message.answer(
        "🔮 *Этот бот объединяет:*\n\n"
        "• нумерологию\n"
        "• совместимость\n"
        "• энергетические прогнозы\n"
        "• расклады\n"
        "• личные вопросы\n\n"
        "Чтобы помочь вам лучше понять:\n"
        "себя, отношения и происходящие события.\n\n"
        "_Что привело вас сюда?_",
        reply_markup=_screen2_kb(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("ob:3:"))
async def ob_screen3(callback: CallbackQuery):
    interest = callback.data.split(":")[-1]
    text = SCREEN3_TEXTS.get(interest, SCREEN3_TEXTS["self"])
    await callback.message.edit_text(text, reply_markup=_screen3_kb(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "ob:4")
async def ob_screen4(callback: CallbackQuery):
    await callback.message.edit_text(
        "✨ *Перед тем как открыть доступ к функциям,*\n"
        "выберите что вас интересует сейчас больше всего:",
        reply_markup=_screen4_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ob:5:"))
async def ob_screen5_animation(callback: CallbackQuery, user: User, session: AsyncSession):
    interest = callback.data.split(":")[-1]

    # Анимация ожидания
    try:
        await callback.message.edit_text("✨ Анализирую вашу энергетику...")
        await asyncio.sleep(1.5)
        await callback.message.edit_text("🌙 Считываю энергетические линии...")
        await asyncio.sleep(1.5)
        await callback.message.edit_text("🔮 Формирую персональное пространство...")
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
        await ensure_keyboard(callback.message, user.telegram_id)
        return

    # Сразу открываем главное меню — без промежуточного экрана
    from bot.keyboards.main import main_menu
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import set_menu_msg_id
    from bot.utils import ensure_keyboard

    name = user.first_name or None
    await callback.message.edit_text(
        _welcome_text(name),
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await set_menu_msg_id(user.telegram_id, callback.message.message_id)
    await ensure_keyboard(callback.message, user.telegram_id)
    await callback.answer()


@router.callback_query(F.data == "ob:open_menu")
async def ob_open_menu(callback: CallbackQuery, user: User):
    """Завершить онбординг → главное меню с полным welcome-текстом как /start."""
    from bot.keyboards.main import main_menu
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import set_menu_msg_id
    from bot.utils import ensure_keyboard

    name = user.first_name or None

    # Редактируем последнее сообщение онбординга в полное приветствие (/start-стиль)
    await callback.message.edit_text(
        _welcome_text(name),
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    # Отслеживаем как меню-сообщение
    await set_menu_msg_id(user.telegram_id, callback.message.message_id)
    # Reply keyboard — только 1 раз за всё время
    await ensure_keyboard(callback.message, user.telegram_id)
    await callback.answer()
