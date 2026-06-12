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

    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    if not await has_credit(user.id, "mini_reading"):
        _locked = {
            "ru": (
                "📖 *Мини-разбор*\n\n"
                "Я посмотрю одну сферу вашей жизни — отношения, деньги, работу, здоровье или другое — "
                "и дам глубокий разбор с учётом ваших личных чисел.\n\n"
                "Что мешает. Что помогает. Что делать.\n\n"
                "💳 Стоимость: *49 ₽* или *49 ⭐*"
            ),
            "en": (
                "📖 *Mini Reading*\n\n"
                "I will look at one area of your life — relationships, money, work, health or other — "
                "and give a deep reading based on your personal numbers.\n\n"
                "What's blocking you. What helps. What to do.\n\n"
                "💳 Price: *49 ⭐*"
            ),
            "fa": (
                "📖 *تحلیل کوتاه*\n\n"
                "یک حوزه از زندگی شما را بررسی می‌کنم — روابط، پول، کار، سلامتی یا موارد دیگر — "
                "و تحلیل عمیقی بر اساس اعداد شخصی شما ارائه می‌دهم.\n\n"
                "💳 قیمت: *49 ⭐*"
            ),
            "tr": (
                "📖 *Mini Yorum*\n\n"
                "Hayatınızın bir alanına bakacağım — ilişkiler, para, iş, sağlık veya başka bir şey — "
                "ve kişisel sayılarınıza dayalı derin bir yorum sunacağım.\n\n"
                "💳 Fiyat: *49 ⭐*"
            ),
        }.get(lang, "📖 *Mini Reading*\n\nA deep look at one area of your life.\n\n💳 Price: *49 ⭐*")
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("mini_reading", 49, 49, lang), parse_mode="Markdown")
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

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    sphere_label = _sphere(sphere, lang)
    sphere_label_ru = SPHERE_NAMES.get(sphere, sphere)  # для кэша/истории всегда ru

    if not cached:
        nums = numerology.calculate_all(birth_date)
        traits = numerology.get_traits(nums["life_path"])
        context = {
            "name": user.first_name or _friend,
            "birth_date": user.birth_date,
            "sphere": sphere_label,
            "numbers": nums,
            "traits": traits,
        }
        user_msg = f"Сделай бесплатный разбор для сферы '{sphere_label}'.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(session, user.id, "free_reading", FREE_BIRTH_REPORT_PROMPT(lang), user_msg, complexity="simple", max_tokens=400)
        await set_cached(cache_key, cached, ttl=3600 * 24 * 3)

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "mini_report",
        title=f"Разбор: {sphere_label_ru}",
        content=cached,
        metadata={"sphere": sphere, "birth_date": user.birth_date},
    )
    from bot.services.limits import use_credit
    await use_credit(user.id, "mini_reading")

    name = user.first_name or _friend
    _title = {"ru": "Разбор для", "en": "Reading for", "fa": "بررسی برای", "tr": "Okuma:"}.get(lang, "Reading for")
    text = f"🔮 *{_title} {name}*\n\n{cached}"

    # CTA кнопка встроена прямо в клавиатуру — не нужен лишний API-вызов
    from bot.keyboards.main import upsell_keyboard_reading
    await safe_edit_ai(thinking_msg, text, reply_markup=upsell_keyboard_reading())
    await callback.answer()


@router.callback_query(F.data == "matrix:start")
async def matrix_start(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    if not await has_credit(user.id, "full_matrix"):
        _locked = {
            "ru": (
                "🌟 *Матрица судьбы*\n\n"
                "Полный разбор вашего предназначения, кармы и сильных сторон.\n\n"
                "Я рассмотрю все ключевые точки вашей карты — таланты, задачи, кармические уроки, "
                "сильные и слабые энергии.\n\n"
                "Самый глубокий анализ из всех доступных разборов.\n\n"
                "💳 Стоимость: *199 ₽* или *199 ⭐*"
            ),
            "en": (
                "🌟 *Destiny Matrix*\n\n"
                "A full reading of your purpose, karma and strengths.\n\n"
                "I will examine all the key points of your map — talents, life tasks, karmic lessons, "
                "strong and weak energies.\n\n"
                "The deepest analysis available.\n\n"
                "💳 Price: *199 ⭐*"
            ),
            "fa": (
                "🌟 *ماتریس سرنوشت*\n\n"
                "تحلیل کامل هدف، کارما و نقاط قوت شما.\n\n"
                "تمام نقاط کلیدی نقشه شما را بررسی می‌کنم — استعدادها، وظایف زندگی، درس‌های کارمایی.\n\n"
                "💳 قیمت: *199 ⭐*"
            ),
            "tr": (
                "🌟 *Kader Matrisi*\n\n"
                "Amacınızın, karmanızın ve güçlü yönlerinizin tam analizi.\n\n"
                "Haritanızın tüm önemli noktalarını inceleyeceğim — yetenekler, yaşam görevleri, karmik dersler.\n\n"
                "💳 Fiyat: *199 ⭐*"
            ),
        }.get(lang, "🌟 *Destiny Matrix*\n\nThe deepest analysis of your purpose and karma.\n\n💳 Price: *199 ⭐*")
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("full_matrix", 199, 199, lang), parse_mode="Markdown")
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
        cached = await generate(session, user.id, "full_matrix", FULL_MATRIX_PROMPT(lang), user_msg, complexity="complex", max_tokens=900)
        await set_cached(cache_key, cached, ttl=3600 * 24 * 7)

    from bot.services.reports_service import save_report as _save
    await _save(
        session, user.id, "destiny_matrix",
        title="Матрица судьбы",
        content=cached,
        metadata={"birth_date": user.birth_date},
    )
    from bot.services.limits import use_credit
    await use_credit(user.id, "full_matrix")

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _matrix_title = {"ru": "Матрица судьбы", "en": "Destiny Matrix", "fa": "ماتریس سرنوشت", "tr": "Kader Matrisi"}.get(lang, "Destiny Matrix")
    text = f"🌟 *{_matrix_title} — {name}*\n\n{cached}"
    await safe_edit_ai(thinking_msg, text, reply_markup=after_reading_keyboard_matrix())
    await callback.answer()


async def show_free_reading(msg: Message, user: User, session, lang: str = "ru"):
    await show_sphere_selection(msg, user, lang)
