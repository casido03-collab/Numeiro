"""FSM: сбор даты рождения и пола."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, datetime
from bot.keyboards.main import gender_keyboard, main_menu, cancel_fsm_keyboard, sphere_menu
from bot.keyboards.reply import ALL_REPLY_TEXTS as _ALL_REPLY
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
    callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, lang: str = "ru"
):
    """Запросить дату рождения и после сохранения вернуть в нужный раздел."""
    return_to = callback.data[len("birth_date:collect:"):]

    if user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        label = _SECTION_LABELS.get(return_to, "▶️ Продолжить")
        _already = {
            "ru": "✅ Дата рождения уже указана. Нажмите чтобы продолжить:",
            "en": "✅ Birth date is already set. Press to continue:",
            "fa": "✅ تاریخ تولد قبلاً ثبت شده است. برای ادامه کلیک کنید:",
            "tr": "✅ Doğum tarihi zaten girilmiş. Devam etmek için tıklayın:",
        }.get(lang, "✅ Birth date is already set. Press to continue:")
        await callback.message.edit_text(
            _already,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=label, callback_data=return_to)],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    _prompt = {
        "ru": "✨ *Введите вашу дату рождения* в формате ДД.ММ.ГГГГ\n\nНапример: *15.03.1995*",
        "en": "✨ *Enter your date of birth* in DD.MM.YYYY format\n\nExample: *15.03.1995*",
        "fa": "✨ *تاریخ تولد خود را وارد کنید* به فرمت روز.ماه.سال\n\nمثال: *15.03.1995*",
        "tr": "✨ *Doğum tarihinizi girin* GG.AA.YYYY formatında\n\nÖrnek: *15.03.1995*",
    }.get(lang, "✨ *Enter your date of birth* in DD.MM.YYYY format\n\nExample: *15.03.1995*")
    await callback.message.edit_text(_prompt, reply_markup=cancel_fsm_keyboard(), parse_mode="Markdown")
    await state.set_state(ProfileFSM.waiting_birth_date)
    await state.update_data(next_action=return_to, origin_chat_id=callback.message.chat.id, lang=lang)
    await callback.answer()


# ─── Запуск бесплатного разбора ───────────────────────────────────────────────

@router.callback_query(F.data == "free:start")
async def free_start(callback: CallbackQuery, user: User, state: FSMContext, session: AsyncSession, lang: str = "ru"):
    _sphere_label = {"ru": "🔮 *Выбери сферу для разбора:*", "en": "🔮 *Choose a sphere for the reading:*",
                     "fa": "🔮 *حوزه‌ای برای تفسیر انتخاب کنید:*", "tr": "🔮 *Okuma için bir alan seçin:*"}.get(lang, "🔮 *Choose a sphere for the reading:*")
    if user.birth_date:
        await callback.message.edit_text(_sphere_label, reply_markup=sphere_menu("sphere", back="menu:main"), parse_mode="Markdown")
        await callback.answer()
        return

    _prompt = {
        "ru": "✨ *Введите вашу дату рождения* в формате ДД.ММ.ГГГГ\n\nНапример: *15.03.1995*",
        "en": "✨ *Enter your date of birth* in DD.MM.YYYY format\n\nExample: *15.03.1995*",
        "fa": "✨ *تاریخ تولد خود را وارد کنید* به فرمت روز.ماه.سال\n\nمثال: *15.03.1995*",
        "tr": "✨ *Doğum tarihinizi girin* GG.AA.YYYY formatında\n\nÖrnek: *15.03.1995*",
    }.get(lang, "✨ *Enter your date of birth* in DD.MM.YYYY format\n\nExample: *15.03.1995*")
    await callback.message.edit_text(_prompt, reply_markup=cancel_fsm_keyboard(), parse_mode="Markdown")
    await state.set_state(ProfileFSM.waiting_birth_date)
    await state.update_data(next_action="free_reading", origin_chat_id=callback.message.chat.id, lang=lang)
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


async def _navigate_to_section(section: str, callback, user, session, state=None) -> None:
    """Открыть нужный раздел сразу после ввода профиля — без промежуточных экранов."""
    if section == "menu:daily":
        from bot.handlers.daily import daily_forecast
        await daily_forecast(callback, user, session)
    elif section == "menu:weekly":
        from bot.handlers.weekly import weekly_start
        await weekly_start(callback, user, session)
    elif section == "menu:horoscope":
        from bot.handlers.horoscope import horoscope_menu
        await horoscope_menu(callback, user, session)
    elif section == "menu:tarot":
        from bot.handlers.tarot import tarot_menu
        await tarot_menu(callback, user, session)
    elif section == "menu:compatibility":
        from bot.handlers.compatibility import compat_start
        if state is not None:
            await compat_start(callback, user, session, state)
        else:
            # Показываем меню без FSM
            await callback.message.edit_text(
                "💞 *Совместимость*\n\nНажми кнопку ниже чтобы начать:",
                reply_markup=_return_keyboard(section),
                parse_mode="Markdown",
            )
    elif section == "matrix:start":
        from bot.handlers.reading import show_sphere_selection
        await show_sphere_selection(callback.message, user)
    else:
        name = user.first_name or "друг"
        await callback.message.edit_text(
            f"✅ Профиль сохранён, *{name}*!",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )


# ─── Получение даты рождения ──────────────────────────────────────────────────

_MENU_TEXTS = _ALL_REPLY


@router.message(ProfileFSM.waiting_birth_date, ~F.text.in_(_ALL_REPLY))
async def receive_birth_date(message: Message, state: FSMContext, user: User, session: AsyncSession):
    _fsm = await state.get_data()
    lang: str = _fsm.get("lang", "ru")

    birth_date = _parse_date(message.text or "")
    if not birth_date:
        _bad = {
            "ru": "❌ Не могу распознать дату. Введите в формате *ДД.ММ.ГГГГ*\n\nНапример: *15.03.1995*",
            "en": "❌ Can't recognize the date. Enter in DD.MM.YYYY format\n\nExample: *15.03.1995*",
            "fa": "❌ تاریخ شناسایی نشد. به فرمت وارد کنید: روز.ماه.سال\n\nمثال: *15.03.1995*",
            "tr": "❌ Tarih tanınamadı. GG.AA.YYYY formatında girin\n\nÖrnek: *15.03.1995*",
        }.get(lang, "❌ Can't recognize the date. Enter in DD.MM.YYYY format\n\nExample: *15.03.1995*")
        await message.answer(_bad, reply_markup=cancel_fsm_keyboard(), parse_mode="Markdown")
        return

    if birth_date.year < 1900 or birth_date > date.today():
        _invalid = {
            "ru": "❌ Пожалуйста, введите корректную дату рождения.",
            "en": "❌ Please enter a valid date of birth.",
            "fa": "❌ لطفاً یک تاریخ تولد معتبر وارد کنید.",
            "tr": "❌ Lütfen geçerli bir doğum tarihi girin.",
        }.get(lang, "❌ Please enter a valid date of birth.")
        await message.answer(_invalid, reply_markup=cancel_fsm_keyboard())
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

    _gender_prompt = {
        "ru": "✨ Отлично! Уточни свой пол для более точного разбора:",
        "en": "✨ Great! Please specify your gender for a more accurate reading:",
        "fa": "✨ عالی! جنسیت خود را برای تفسیر دقیق‌تر مشخص کنید:",
        "tr": "✨ Harika! Daha doğru bir okuma için cinsiyetinizi belirtin:",
    }.get(lang, "✨ Great! Please specify your gender for a more accurate reading:")
    await message.answer(_gender_prompt, reply_markup=gender_keyboard())
    await state.update_data(lang=lang)
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
    lang: str = data.get("lang", "ru")
    await state.clear()

    _sphere_label = {"ru": "🔮 *Выбери сферу для разбора:*", "en": "🔮 *Choose a sphere for the reading:*",
                     "fa": "🔮 *حوزه‌ای برای تفسیر انتخاب کنید:*", "tr": "🔮 *Okuma için bir alan seçin:*"}.get(lang, "🔮 *Choose a sphere for the reading:*")

    if next_action == "free_reading":
        await callback.message.edit_text(_sphere_label, reply_markup=sphere_menu("sphere", back="menu:main"), parse_mode="Markdown")
    elif next_action and (next_action.startswith("menu:") or next_action == "matrix:start"):
        await _navigate_to_section(next_action, callback, user, session, state)
    else:
        _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
        name = user.first_name or _friend
        _saved = {
            "ru": f"✅ Профиль сохранён! Выберите что вас интересует, *{name}*:",
            "en": f"✅ Profile saved! Choose what interests you, *{name}*:",
            "fa": f"✅ پروفایل ذخیره شد! *{name}*، چه چیزی برایتان جالب است:",
            "tr": f"✅ Profil kaydedildi! *{name}*, sizi ne ilgilendiriyor:",
        }.get(lang, f"✅ Profile saved! Choose what interests you, *{name}*:")
        await callback.message.edit_text(_saved, reply_markup=main_menu(), parse_mode="Markdown")

    await callback.answer()
