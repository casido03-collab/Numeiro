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
from bot.i18n.translations import t
from bot.keyboards.main import event_type_menu, limit_reached_keyboard, back_to_main
from bot.utils import safe_edit, safe_edit_ai
from bot.services.thinking import random_thinking

router = Router()


@router.callback_query(F.data == "menu:dates")
async def dates_menu(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    if not await has_credit(user.id, "date_selection"):
        _locked = {
            "ru": "🔒 *Подбор дат*\n\nДоступно за *99 ₽* или *99 ⭐*",
            "en": "🔒 *Date Selection*\n\nAvailable for *99 ⭐*",
            "fa": "🔒 *انتخاب تاریخ*\n\nقابل دسترس برای *99 ⭐*",
            "tr": "🔒 *Tarih Seçimi*\n\n*99 ⭐* karşılığında erişilebilir",
        }.get(lang, "🔒 *Date Selection*\n\nAvailable for *99 ⭐*")
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("date_selection", 99, 99, lang), parse_mode="Markdown")
        await callback.answer()
        return

    _dates_prompt = {
        "ru": "📆 *Подбор благоприятных дат*\n\nВыбери событие:",
        "en": "📆 *Favorable date selection*\n\nChoose an event:",
        "fa": "📆 *انتخاب تاریخ مناسب*\n\nیک رویداد انتخاب کنید:",
        "tr": "📆 *Uygun tarih seçimi*\n\nBir etkinlik seçin:",
    }.get(lang, "📆 *Favorable date selection*\n\nChoose an event:")
    await callback.message.edit_text(
        _dates_prompt,
        reply_markup=event_type_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("dates:event:"))
async def select_event(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    event_type = callback.data.split(":")[-1]

    from bot.services.limits import has_credit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    if not await has_credit(user.id, "date_selection"):
        await callback.message.edit_text(
            "🔒 *Подбор дат*\n\nДоступно за *99 ₽* или *99 ⭐*",
            reply_markup=_pay_kb("date_selection", 99, 99, lang),
            parse_mode="Markdown",
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
        DATE_SELECTION_PROMPT(lang), user_msg,
        complexity="simple", max_tokens=400,
    )

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "date_selection",
        title=f"Подбор дат: {event_name}",
        content=response,
        metadata={"event": event_type, "event_name": event_name},
    )
    from bot.services.limits import use_credit
    await use_credit(user.id, "date_selection")

    dates_list = "\n".join(
        f"• *{d['date']}* ({d['weekday']}) — энергия {d['energy']}" for d in favorable
    )
    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _hdr = {"ru": "Благоприятные даты для", "en": "Favorable dates for", "fa": "تاریخ‌های مناسب برای", "tr": "Uygun tarihler:"}.get(lang, "Favorable dates for")
    _ev_label = {"ru": "Событие", "en": "Event", "fa": "رویداد", "tr": "Etkinlik"}.get(lang, "Event")
    header = f"📆 *{_hdr} — {name}*\n_{_ev_label}: {event_name}_\n\n{dates_list}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Выбрать другое событие", callback_data="menu:dates")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])
    await safe_edit_ai(thinking_msg, header + response, reply_markup=kb)
    await callback.answer()
