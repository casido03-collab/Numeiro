"""Личный вопрос к судьбе — FSM."""
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.numerology import calculate_all
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.prompts.prompts import PERSONAL_QUESTION_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import limit_reached_keyboard, after_reading_keyboard, after_question_keyboard_free, after_question_keyboard_paid, back_to_main, main_menu
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai, replace_message
from bot.services.thinking import random_thinking
from bot.keyboards.reply import ALL_REPLY_TEXTS as _ALL_REPLY

router = Router()


class QuestionFSM(StatesGroup):
    waiting_birth_date = State()  # ввод даты рождения перед вопросом
    waiting_question   = State()


@router.callback_query(F.data == "question:cancel")
async def question_cancel(callback: CallbackQuery, state: FSMContext, user: User):
    await state.clear()
    name = user.first_name or "друг"
    await replace_message(
        callback.message,
        f"✨ *{name}*, выберите что вас интересует:",
        reply_markup=main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:question")
async def question_start(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext, lang: str = "ru"):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    if not await has_credit(user.id, "personal_question"):
        _locked = {
            "ru": (
                "🔮 *Личный расклад*\n\n"
                "Добро пожаловать, мои хорошие.\n\n"
                "Сейчас Вы можете задать мне свой вопрос и получить индивидуальный разбор ситуации.\n\n"
                "Чем подробнее Вы опишете ситуацию, тем глубже я смогу её рассмотреть.\n\n"
                "Например:\n\n"
                "❤️ Что чувствует ко мне этот человек?\n"
                "💼 Стоит ли принимать новое предложение?\n"
                "🌙 Что ожидает меня в ближайшее время?\n"
                "⭐ На что мне стоит обратить внимание сейчас?\n\n"
                "💳 Стоимость: *29 ₽* или *29 ⭐*"
            ),
            "en": (
                "🔮 *Personal Reading*\n\n"
                "Welcome, dear ones.\n\n"
                "You can ask me your question and receive a personal reading of your situation.\n\n"
                "The more detail you provide, the deeper I can look into it.\n\n"
                "For example:\n\n"
                "❤️ What does this person feel for me?\n"
                "💼 Should I accept the new offer?\n"
                "🌙 What awaits me in the near future?\n"
                "⭐ What should I pay attention to right now?\n\n"
                "💳 Price: *29 ⭐*"
            ),
            "fa": (
                "🔮 *خواندن شخصی*\n\n"
                "خوش آمدید، عزیزانم.\n\n"
                "می‌توانید سؤال خود را بپرسید و تفسیر شخصی دریافت کنید.\n\n"
                "هرچه بیشتر توضیح دهید، عمیق‌تر می‌توانم بررسی کنم.\n\n"
                "مثلاً:\n\n"
                "❤️ این شخص چه احساسی نسبت به من دارد؟\n"
                "💼 آیا باید پیشنهاد جدید را بپذیرم؟\n"
                "🌙 در آینده نزدیک چه چیزی در انتظار من است؟\n\n"
                "💳 قیمت: *29 ⭐*"
            ),
            "tr": (
                "🔮 *Kişisel Okuma*\n\n"
                "Hoş geldiniz, canlarım.\n\n"
                "Sorunuzu sorabilir ve durumunuz için kişisel bir yorum alabilirsiniz.\n\n"
                "Ne kadar ayrıntı verirseniz, o kadar derin bakabilirim.\n\n"
                "Örneğin:\n\n"
                "❤️ Bu kişi benim için ne hissediyor?\n"
                "💼 Yeni teklifi kabul etmeli miyim?\n"
                "🌙 Yakın gelecekte beni ne bekliyor?\n"
                "⭐ Şu an neye dikkat etmeliyim?\n\n"
                "💳 Fiyat: *29 ⭐*"
            ),
        }.get(lang, "🔮 *Personal Reading*\n\nAsk me your question and receive a personal reading.\n\n💳 Price: *29 ⭐*")
        await replace_message(callback.message, _locked, reply_markup=_pay_kb("personal_question", 29, 29, lang))
        await callback.answer()
        return

    if not user.birth_date:
        await replace_message(
            callback.message,
            "✨ Для персонального разбора нужна ваша дата рождения.\n\nВведите в формате *ДД.ММ.ГГГГ*\nНапример: 15.03.1990",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
        )
        await state.set_state(QuestionFSM.waiting_birth_date)
        await callback.answer()
        return

    await state.update_data(lang=lang)
    _write_label = {"ru": "📝 Напишите свой вопрос сообщением ниже", "en": "📝 Write your question in the next message",
                    "fa": "📝 سؤال خود را در پیام بعدی بنویسید", "tr": "📝 Sorunuzu bir sonraki mesajda yazın"}.get(lang, "📝 Write your question")
    _welcome = {
        "ru": (
            "🔮 *Личный расклад*\n\n"
            "Добро пожаловать, мои хорошие.\n\n"
            "Сейчас Вы можете задать мне свой вопрос и получить индивидуальный разбор ситуации.\n\n"
            "Чем подробнее Вы опишете ситуацию, тем глубже я смогу её рассмотреть.\n\n"
            "Например:\n\n"
            "❤️ Что чувствует ко мне этот человек?\n"
            "💼 Стоит ли принимать новое предложение?\n"
            "🌙 Что ожидает меня в ближайшее время?\n"
            "⭐ На что мне стоит обратить внимание сейчас?\n\n"
            f"{_write_label}"
        ),
        "en": (
            "🔮 *Personal reading*\n\n"
            "Welcome, dear ones.\n\n"
            "You can now ask me your question and receive a personal reading of your situation.\n\n"
            "The more detail you provide, the deeper I can look into it.\n\n"
            "For example:\n\n"
            "❤️ What does this person feel for me?\n"
            "💼 Should I accept the new offer?\n"
            "🌙 What awaits me in the near future?\n"
            "⭐ What should I pay attention to right now?\n\n"
            f"{_write_label}"
        ),
        "fa": (
            "🔮 *خواندن شخصی*\n\n"
            "خوش آمدید، عزیزانم.\n\n"
            "می‌توانید سؤال خود را بپرسید و تفسیر شخصی دریافت کنید.\n\n"
            "هرچه بیشتر توضیح دهید، عمیق‌تر می‌توانم بررسی کنم.\n\n"
            f"{_write_label}"
        ),
        "tr": (
            "🔮 *Kişisel okuma*\n\n"
            "Hoş geldiniz, canlarım.\n\n"
            "Sorunuzu sorabilir ve kişisel bir yorum alabilirsiniz.\n\n"
            "Ne kadar ayrıntı verirseniz, o kadar derin bakabilirim.\n\n"
            f"{_write_label}"
        ),
    }.get(lang, f"🔮 *Personal reading*\n\n{_write_label}")
    await replace_message(
        callback.message,
        _welcome,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="question:cancel")]
        ]),
    )
    await state.set_state(QuestionFSM.waiting_question)
    await callback.answer()


@router.message(QuestionFSM.waiting_birth_date, ~F.text.in_(_ALL_REPLY))
async def receive_birth_date_for_question(message: Message, state: FSMContext, user: User, session: AsyncSession):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.services.limits import check_limit
    from datetime import datetime

    text = (message.text or "").strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату так: *15.03.1990*", parse_mode="Markdown")
        return

    # Сохраняем дату рождения
    user.birth_date = dt
    await session.commit()

    # Теперь показываем экран вопроса
    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    if not await has_credit(user.id, "personal_question"):
        await state.clear()
        await message.answer(
            "🔒 *Личный вопрос*\n\nДоступно за *29 ₽* или *29 ⭐*",
            reply_markup=_pay_kb("personal_question", 29, 29, "ru"),
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "🔮 *Личный расклад*\n\n"
        "Добро пожаловать, мои хорошие.\n\n"
        "📝 Напишите свой вопрос сообщением ниже",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="question:cancel")]
        ]),
        parse_mode="Markdown",
    )
    await state.set_state(QuestionFSM.waiting_question)


@router.message(QuestionFSM.waiting_question, ~F.text.in_(_ALL_REPLY))
async def receive_question(message: Message, state: FSMContext, user: User, session: AsyncSession, lang: str = "ru"):
    _fsm = await state.get_data()
    lang = _fsm.get("lang", lang)

    question = (message.text or "").strip()
    _too_short = {"ru": "❌ Вопрос слишком короткий. Попробуй снова.", "en": "❌ Question is too short. Please try again.",
                  "fa": "❌ سؤال خیلی کوتاه است. دوباره امتحان کنید.", "tr": "❌ Soru çok kısa. Lütfen tekrar deneyin."}.get(lang, "❌ Question is too short.")
    _too_long = {"ru": "❌ Вопрос слишком длинный (максимум 500 символов).", "en": "❌ Question is too long (max 500 characters).",
                 "fa": "❌ سؤال خیلی طولانی است (حداکثر ۵۰۰ کاراکتر).", "tr": "❌ Soru çok uzun (en fazla 500 karakter)."}.get(lang, "❌ Question is too long.")
    if len(question) < 5:
        await message.answer(_too_short)
        return
    if len(question) > 500:
        await message.answer(_too_long)
        return

    await state.clear()
    thinking_msg = await message.answer(random_thinking())

    birth_date_obj = parse_birth_date(user.birth_date)

    nums = calculate_all(birth_date_obj) if birth_date_obj else {}
    context = {
        "name": user.first_name or "друг",
        "birth_date": user.birth_date or "неизвестно",
        "question": question,
        "numbers": {k: v for k, v in nums.items() if k in ["life_path", "destiny", "personality"]},
    }

    from bot.services.limits import get_user_plan
    from bot.prompts.prompts import PERSONAL_QUESTION_PAID_PROMPT
    plan = await get_user_plan(session, user.id)
    is_paid = plan != "free"

    prompt     = PERSONAL_QUESTION_PAID_PROMPT(lang) if is_paid else PERSONAL_QUESTION_PROMPT(lang)
    max_tokens = 600 if is_paid else 450

    user_msg = f"Ответь на личный вопрос пользователя.\nДанные: {json.dumps(context, ensure_ascii=False)}"
    response = await generate(
        session, user.id, "personal_question",
        prompt, user_msg,
        complexity="medium", max_tokens=max_tokens,
    )

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "personal_question",
        title=f"Вопрос: {question[:70]}{'…' if len(question) > 70 else ''}",
        content=response,
        metadata={"question": question},
    )
    from bot.services.limits import use_credit
    await use_credit(user.id, "personal_question")

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _ans_title = {"ru": "Ответ для", "en": "Answer for", "fa": "پاسخ برای", "tr": "Cevap:"}.get(lang, "Answer for")
    _q_label = {"ru": "Вопрос", "en": "Question", "fa": "سؤال", "tr": "Soru"}.get(lang, "Question")
    text = f"🔮 *{_ans_title} {name}*\n_{_q_label}: {question}_\n\n{response}"
    kb = after_question_keyboard_paid() if is_paid else after_question_keyboard_free()
    await safe_edit_ai(thinking_msg, text, reply_markup=kb)
