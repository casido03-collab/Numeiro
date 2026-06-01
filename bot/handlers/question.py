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
from bot.keyboards.main import limit_reached_keyboard, after_reading_keyboard, back_to_main, main_menu
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai, replace_message
from bot.services.thinking import random_thinking

router = Router()


class QuestionFSM(StatesGroup):
    waiting_question = State()


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
async def question_start(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
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
            "✨ Сначала укажи дату рождения.\n\nВведи в формате *ДД.ММ.ГГГГ*",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
        )
        await callback.answer()
        return

    remaining = max_val - used
    await replace_message(
        callback.message,
        f"🔮 *Личный расклад*\n\n"
        f"Добро пожаловать, мои хорошие.\n\n"
        f"Сейчас Вы можете задать мне свой вопрос и получить индивидуальный разбор ситуации.\n\n"
        f"✨ Доступно вопросов: *{remaining}*\n\n"
        f"Чем подробнее Вы опишете ситуацию, тем глубже я смогу её рассмотреть.\n\n"
        f"Например:\n\n"
        f"❤️ Что чувствует ко мне этот человек?\n"
        f"💼 Стоит ли принимать новое предложение?\n"
        f"🌙 Что ожидает меня в ближайшее время?\n"
        f"⭐ На что мне стоит обратить внимание сейчас?\n\n"
        f"📝 Напишите свой вопрос сообщением ниже",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="question:cancel")]
        ]),
    )
    await state.set_state(QuestionFSM.waiting_question)
    await callback.answer()


@router.message(QuestionFSM.waiting_question, ~F.text.in_({"🔮 Меню", "📚 Интересное", "👥 Друзья", "💎 Подписка"}))
async def receive_question(message: Message, state: FSMContext, user: User, session: AsyncSession):
    question = (message.text or "").strip()
    if len(question) < 5:
        await message.answer("❌ Вопрос слишком короткий. Попробуй снова.")
        return
    if len(question) > 500:
        await message.answer("❌ Вопрос слишком длинный (максимум 500 символов).")
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

    user_msg = f"Ответь на личный вопрос пользователя.\nДанные: {json.dumps(context, ensure_ascii=False)}"
    response = await generate(
        session, user.id, "personal_question",
        PERSONAL_QUESTION_PROMPT, user_msg,
        complexity="medium", max_tokens=450,
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

    name = user.first_name or "друг"
    text = f"🔮 *Ответ для {name}*\n_Вопрос: {question}_\n\n{response}"
    await safe_edit_ai(thinking_msg, text, reply_markup=after_reading_keyboard())
