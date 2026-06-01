"""FSM: сбор даты рождения и пола."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, datetime
from bot.keyboards.main import gender_keyboard, main_menu, cancel_fsm_keyboard, sphere_menu
from bot.models.user import User, UserProfile
from bot.services.numerology import calculate_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = Router()


class ProfileFSM(StatesGroup):
    waiting_birth_date = State()
    waiting_gender = State()


def _parse_date(text: str) -> date | None:
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


_SECTION_LABELS = {
    "menu:daily":         "⚡ Энергия дня",
    "menu:weekly":        "📅 Расклад на неделю",
    "menu:horoscope":     "🔯 Гороскоп",
    "menu:tarot":         "🃏 Карта дня",
    "menu:compatibility": "💞 Совместимость",
    "menu:question":      "🔮 Задать вопрос",
    "matrix:start":       "🌟 Матрица судьбы",
}


def _return_keyboard(callback_data: str):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    label = _SECTION_LABELS.get(callback_data, "▶️ Продолжить")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=callback_data)],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


# ─── Универсальный сбор даты рождения с возвратом в раздел ────────────────────

@router.callback_query(F.data.startswith("birth_date:collect:"))
async def collect_birth_date_for_section(
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession
):
    """Запросить дату рождения и после сохранения вернуть в нужный раздел."""
    return_to = callback.data[len("birth_date:collect:"):]

    if user.birth_date:
        # Дата уже есть — сразу в нужный раздел
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        label = _SECTION_LABELS.get(return_to, "▶️ Продолжить")
        await callback.message.edit_text(
            "✅ Дата рождения уже указана. Нажмите чтобы продолжить:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=label, callback_data=return_to)],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "✨ *Введите вашу дату рождения* в формате ДД.ММ.ГГГГ\n\nНапример: *15.03.1995*",
        reply_markup=cancel_fsm_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(ProfileFSM.waiting_birth_date)
    await state.update_data(next_action=return_to, origin_chat_id=callback.message.chat.id)
    await callback.answer()


# ─── Запуск бесплатного разбора ───────────────────────────────────────────────

@router.callback_query(F.data == "free:start")
async def free_start(callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession):
    if user.birth_date:
        # Уже есть дата — сразу к выбору сферы
        await callback.message.edit_text(
            "🔮 *Выбери сферу для разбора:*",
            reply_markup=sphere_menu("sphere", back="menu:main"),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "✨ *Введите вашу дату рождения* в формате ДД.ММ.ГГГГ\n\nНапример: *15.03.1995*",
        reply_markup=cancel_fsm_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(ProfileFSM.waiting_birth_date)
    await state.update_data(next_action="free_reading", origin_chat_id=callback.message.chat.id)
    await callback.answer()


# ─── Отмена FSM (кнопка «Назад») ─────────────────────────────────────────────

@router.callback_query(F.data == "profile:cancel")
async def profile_cancel(callback: CallbackQuery, state: FSMContext, user: User):
    await state.clear()
    name = user.first_name or "друг"
    await callback.message.edit_text(
        f"✨ *{name}*, выберите что вас интересует:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Получение даты рождения ──────────────────────────────────────────────────

_MENU_TEXTS = {"🔮 Меню", "📚 Интересное", "👥 Друзья", "💎 Подписка"}


@router.message(ProfileFSM.waiting_birth_date, ~F.text.in_({"🔮 Меню", "📚 Интересное", "👥 Друзья", "💎 Подписка"}))
async def receive_birth_date(message: Message, state: FSMContext, user: User, session: AsyncSession):
    birth_date = _parse_date(message.text or "")
    if not birth_date:
        await message.answer(
            "❌ Не могу распознать дату. Введите в формате *ДД.ММ.ГГГГ*\n\nНапример: *15.03.1995*",
            reply_markup=cancel_fsm_keyboard(),
            parse_mode="Markdown",
        )
        return

    if birth_date.year < 1900 or birth_date > date.today():
        await message.answer(
            "❌ Пожалуйста, введите корректную дату рождения.",
            reply_markup=cancel_fsm_keyboard(),
        )
        return

    user.birth_date = birth_date.strftime("%d.%m.%Y")

    # Считаем числа и сохраняем
    nums = calculate_all(birth_date)
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile:
        profile.life_path_number = nums["life_path"]
        profile.destiny_number = nums["destiny"]
        profile.personality_number = nums["personality"]

    await session.commit()

    await message.answer(
        "✨ Отлично! Уточни свой пол для более точного разбора:",
        reply_markup=gender_keyboard(),
    )
    await state.set_state(ProfileFSM.waiting_gender)


# ─── Получение пола ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("profile:gender:"), ProfileFSM.waiting_gender)
async def receive_gender(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession):
    gender = callback.data.split(":")[-1]
    from bot.models.user import GenderEnum
    user.gender = GenderEnum(gender)
    await session.commit()

    data = await state.get_data()
    next_action = data.get("next_action", "free_reading")
    await state.clear()

    if next_action == "free_reading":
        await callback.message.edit_text(
            "🔮 *Выбери сферу для разбора:*",
            reply_markup=sphere_menu("sphere", back="menu:main"),
            parse_mode="Markdown",
        )
    elif next_action and next_action.startswith("menu:"):
        # Возврат в конкретный раздел (daily, weekly, tarot и т.д.)
        await callback.message.edit_text(
            "✅ Дата рождения сохранена! Возвращаю вас в раздел…",
            parse_mode="Markdown",
        )
        # Эмулируем нажатие нужной кнопки
        await callback.message.edit_text(
            "✅ *Дата сохранена.* Нажмите кнопку ниже чтобы продолжить:",
            reply_markup=_return_keyboard(next_action),
            parse_mode="Markdown",
        )
    else:
        name = user.first_name or "друг"
        await callback.message.edit_text(
            f"✅ Профиль сохранён! Выберите что вас интересует, *{name}*:",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )

    await callback.answer()
