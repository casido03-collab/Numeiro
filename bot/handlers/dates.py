"""Подбор благоприятных дат."""
import json
from datetime import date
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.dates import find_favorable_dates, EVENT_NAMES
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.prompts.prompts import DATE_SELECTION_PROMPT
from bot.keyboards.main import event_type_menu, limit_reached_keyboard, back_to_main
from bot.utils import safe_edit, safe_edit_ai
from bot.services.thinking import random_thinking

router = Router()


@router.callback_query(F.data == "menu:dates")
async def dates_menu(callback: CallbackQuery, user: User, session: AsyncSession):
    has_limit, used, max_val = await check_limit(session, user.id, "date_selections")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Подбор благоприятных дат*\n\nЭта функция доступна в Premium и Pro тарифах.",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📆 *Подбор благоприятных дат*\n\nВыбери событие:",
        reply_markup=event_type_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dates:event:"))
async def select_event(callback: CallbackQuery, user: User, session: AsyncSession):
    event_type = callback.data.split(":")[-1]

    has_limit, used, max_val = await check_limit(session, user.id, "date_selections")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 Лимит подборов дат исчерпан.",
            reply_markup=limit_reached_keyboard(),
        )
        await callback.answer()
        return

    thinking_msg = await callback.message.edit_text(random_thinking())

    today = date.today()
    favorable = find_favorable_dates(event_type, today, count=5)

    event_name = EVENT_NAMES.get(event_type, event_type)
    context = {
        "name": user.first_name or "друг",
        "event": event_name,
        "dates": [{"date": d["date"], "weekday": d["weekday"], "energy": d["energy"]} for d in favorable],
    }

    user_msg = f"Обоснуй выбор благоприятных дат для события '{event_name}'.\nДанные: {json.dumps(context, ensure_ascii=False)}"
    response = await generate(
        session, user.id, "date_selection",
        DATE_SELECTION_PROMPT, user_msg,
        complexity="simple", max_tokens=400,
    )

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "date_selection",
        title=f"Подбор дат: {event_name}",
        content=response,
        metadata={"event": event_type, "event_name": event_name},
    )
    await consume_limit(session, user.id, "date_selections")
    await consume_limit(session, user.id, "ai_messages")

    dates_list = "\n".join(
        f"• *{d['date']}* ({d['weekday']}) — энергия {d['energy']}" for d in favorable
    )
    name = user.first_name or "друг"
    header = f"📆 *Благоприятные даты для — {name}*\n_Событие: {event_name}_\n\n{dates_list}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Выбрать другое событие", callback_data="menu:dates")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])
    await safe_edit_ai(thinking_msg, header + response, reply_markup=kb)
    await callback.answer()
