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

    has_limit, used, max_val = await check_limit(session, user.id, "personal_questions")
    if not has_limit:
        await replace_message(
            callback.message,
            "🔒 *Вопрос Бабушке Aisha*\n\nЭта функция требует подписки или разовой покупки.\n\n"
            "• Free: 1 вопрос\n"
            "• Lite: 7 вопросов\n"
            "• Premium: 30 вопросов\n"
            "• Pro: 60 вопросов",
            reply_markup=limit_reached_keyboard(),
        )
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
    remaining = max_val - used
    _remaining_label = {"ru": "Доступно вопросов", "en": "Questions remaining", "fa": "سؤالات باقی‌مانده", "tr": "Kalan soru sayısı"}.get(lang, "Questions remaining")
    _write_label = {"ru": "📝 Напишите свой вопрос сообщением ниже", "en": "📝 Write your question in the next message",
                    "fa": "📝 سؤال خود را در پیام بعدی بنویسید", "tr": "📝 Sorunuzu bir sonraki mesajda yazın"}.get(lang, "📝 Write your question")
    _welcome = {
        "ru": (
            f"🔮 *Личный расклад*\n\n"
            f"Добро пожаловать, мои хорошие.\n\n"
            f"Сейчас Вы можете задать мне свой вопрос и получить индивидуальный разбор ситуации.\n\n"
            f"✨ {_remaining_label}: *{remaining}*\n\n"
            f"Чем подробнее Вы опишете ситуацию, тем глубже я смогу её рассмотреть.\n\n"
            f"Например:\n\n"
            f"❤️ Что чувствует ко мне этот человек?\n"
            f"💼 Стоит ли принимать новое предложение?\n"
            f"🌙 Что ожидает меня в ближайшее время?\n"
            f"⭐ На что мне стоит обратить внимание сейчас?\n\n"
            f"{_write_label}"
        ),
        "en": (
            f"🔮 *Personal reading*\n\n"
            f"Welcome, dear ones.\n\n"
            f"You can now ask me your question and receive a personal reading of your situation.\n\n"
            f"✨ {_remaining_label}: *{remaining}*\n\n"
            f"The more detail you provide, the deeper I can look into it.\n\n"
            f"For example:\n\n"
            f"❤️ What does this person feel for me?\n"
            f"💼 Should I accept the new offer?\n"
            f"🌙 What awaits me in the near future?\n"
            f"⭐ What should I pay attention to right now?\n\n"
            f"{_write_label}"
        ),
        "fa": (
            f"🔮 *خواندن شخصی*\n\n"
            f"خوش آمدید، عزیزانم.\n\n"
            f"می‌توانید سؤال خود را بپرسید و تفسیر شخصی دریافت کنید.\n\n"
            f"✨ {_remaining_label}: *{remaining}*\n\n"
            f"هرچه بیشتر توضیح دهید، عمیق‌تر می‌توانم بررسی کنم.\n\n"
            f"{_write_label}"
        ),
        "tr": (
            f"🔮 *Kişisel okuma*\n\n"
            f"Hoş geldiniz, canlarım.\n\n"
            f"Sorunuzu sorabilir ve kişisel bir yorum alabilirsiniz.\n\n"
            f"✨ {_remaining_label}: *{remaining}*\n\n"
            f"Ne kadar ayrıntı verirseniz, o kadar derin bakabilirim.\n\n"
            f"{_write_label}"
        ),
    }.get(lang, f"🔮 *Personal reading*\n\n✨ {_remaining_label}: *{remaining}*\n\n{_write_label}")
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
    has_limit, used, max_val = await check_limit(session, user.id, "personal_questions")
    if not has_limit:
        await state.clear()
        await message.answer(
            "🔒 *Вопрос Бабушке Aisha*\n\nЛимит вопросов исчерпан.\n\n"
            "• Free: 1 вопрос\n• Lite: 7 вопросов\n• Premium: 30 вопросов\n• Pro: 60 вопросов",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        return

    remaining = max_val - used
    await message.answer(
        f"🔮 *Личный расклад*\n\n"
        f"Добро пожаловать, мои хорошие.\n\n"
        f"✨ Доступно вопросов: *{remaining}*\n\n"
        f"📝 Напишите свой вопрос сообщением ниже",
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
    await consume_limit(session, user.id, "personal_questions")
    await consume_limit(session, user.id, "ai_messages")

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _ans_title = {"ru": "Ответ для", "en": "Answer for", "fa": "پاسخ برای", "tr": "Cevap:"}.get(lang, "Answer for")
    _q_label = {"ru": "Вопрос", "en": "Question", "fa": "سؤال", "tr": "Soru"}.get(lang, "Question")
    text = f"🔮 *{_ans_title} {name}*\n_{_q_label}: {question}_\n\n{response}"
    kb = after_question_keyboard_paid() if is_paid else after_question_keyboard_free()
    await safe_edit_ai(thinking_msg, text, reply_markup=kb)
