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
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai

router = Router()


class QuestionFSM(StatesGroup):
    waiting_question = State()


@router.callback_query(F.data == "question:cancel")
async def question_cancel(callback: CallbackQuery, state: FSMContext, user: User):
    await state.clear()
    name = user.first_name or "друг"
    await callback.message.edit_text(
        f"✨ *{name}*, выбери что тебя интересует:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "menu:question")
async def question_start(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    has_limit, used, max_val = await check_limit(session, user.id, "personal_questions")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Вопрос Тарологу*\n\nЭта функция требует подписки или разовой покупки.\n\n"
            "• Lite: 2 вопроса\n"
            "• Premium: 15 вопросов\n"
            "• Pro: 60 вопросов",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    if not user.birth_date:
        await callback.message.edit_text(
            "✨ Сначала укажи дату рождения.\n\nВведи в формате *ДД.ММ.ГГГГ*",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    name = user.first_name or "друг"
    await callback.message.edit_text(
        f"🔮 *{name}*, задай свой вопрос Тарологу.\n\n"
        f"Осталось вопросов: *{max_val - used}*\n\n"
        f"Примеры:\n"
        f"• Стоит ли менять работу?\n"
        f"• Что меня ждёт в отношениях?\n"
        f"• В каком направлении двигаться?\n\n"
        f"Напиши свой вопрос ниже ⬇️",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="question:cancel")]
        ]),
        parse_mode="Markdown",
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
    thinking_msg = await message.answer("🌙 Настраиваюсь на ваш запрос...")

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
