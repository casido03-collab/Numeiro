from bot.services.catalog import product_offer
from bot.services.limits import has_credit as product_has_credit
"""Подбор благоприятных дат."""
import json
from datetime import date, timedelta
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
    from bot.services.limits import has_credit, is_vip, check_vip_limit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    _is_vip = await is_vip(user.id)
    if not _is_vip and not await has_credit(user.id, "date_selection"):
        _locked = product_offer("date_selection", lang)
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("date_selection", 99, 99, lang), parse_mode="Markdown")
        await callback.answer()
        return

    if _is_vip and not await check_vip_limit(user.id, "date_selection") and not await product_has_credit(user.id, "date_selection"):
        _exhausted = {
            "ru": "💎 Лимит VIP по этому разделу исчерпан на этот месяц.",
            "en": "💎 VIP limit for this section exhausted this month.",
            "fa": "💎 محدودیت VIP برای این بخش تمام شده.",
            "tr": "💎 Bu bölüm için VIP limitiniz doldu.",
        }.get(lang, "💎 VIP limit exhausted.")
        await callback.message.edit_text(_exhausted, reply_markup=back_to_main(), parse_mode="Markdown")
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

    if event_type not in EVENT_NAMES or event_type in ("medical", "investment"):
        await callback.answer("Для этого события подбор по числам недоступен.", show_alert=True)
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    labels = {"ru": ("На ближайшие 30 дней", "На ближайшие 60 дней", "Выберите период поиска:"),
              "en": ("Next 30 days", "Next 60 days", "Choose a date range:"),
              "fa": ("۳۰ روز آینده", "۶۰ روز آینده", "بازه زمانی را انتخاب کنید:"),
              "tr": ("Önümüzdeki 30 gün", "Önümüzdeki 60 gün", "Tarih aralığını seçin:")}.get(lang)
    await callback.message.edit_text(labels[2], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels[0], callback_data=f"dates:period:{event_type}:30")],
        [InlineKeyboardButton(text=labels[1], callback_data=f"dates:period:{event_type}:60")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="menu:dates")]]))
    await callback.answer()


@router.callback_query(F.data.startswith("dates:period:"))
async def select_weekdays(callback: CallbackQuery, lang="ru"):
    _, _, event, days = callback.data.split(":")
    if event not in EVENT_NAMES or days not in ("30", "60"):
        await callback.answer()
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    labels = {"ru": ("Любые дни", "Только будни", "Только выходные", "Какие дни вам подходят?"),
              "en": ("Any day", "Weekdays only", "Weekends only", "Which days suit you?"),
              "fa": ("همه روزها", "دوشنبه تا جمعه", "شنبه و یکشنبه", "کدام روزها مناسب‌اند؟"),
              "tr": ("Her gün", "Hafta içi", "Hafta sonu", "Hangi günler size uygun?")}.get(lang)
    await callback.message.edit_text(labels[3], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=labels[i], callback_data=f"dates:run:{event}:{days}:{mode}")]
        for i, mode in enumerate(("all", "workdays", "weekends"))]))
    await callback.answer()


@router.callback_query(F.data.startswith("dates:run:"))
async def generate_dates(callback: CallbackQuery, user: User, session: AsyncSession, lang="ru"):
    _, _, event_type, days, weekday_mode = callback.data.split(":")
    if (event_type not in EVENT_NAMES or event_type in ("medical", "investment")
            or days not in ("30", "60") or weekday_mode not in ("all", "workdays", "weekends")):
        await callback.answer()
        return
    from bot.utils import parse_birth_date
    from bot.services.limits import can_use_product
    from bot.services.fulfillment import PurchaseRequired
    if not await can_use_product(user.id, "date_selection"):
        raise PurchaseRequired("date_selection")

    thinking_msg = await callback.message.edit_text(random_thinking())

    today = date.today()
    favorable = find_favorable_dates(event_type, today, count=5, to_date=today + timedelta(days=int(days)),
                                      weekdays=weekday_mode, birth_date=parse_birth_date(user.birth_date))
    weekday_names = {
        "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
        "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        "fa": ("دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"),
        "tr": ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"),
    }.get(lang, ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
    for item in favorable:
        item["weekday"] = weekday_names[item["weekday"]]

    event_name = EVENT_NAMES.get(event_type, event_type)
    context = {
        "name": user.first_name or "друг",
        "event": event_name,
        "dates": [{"date": d["date"], "weekday": d["weekday"], "energy": d["energy"], "personal_energy": d["personal_energy"]} for d in favorable],
    }

    from bot.services.fulfillment import generate_paid_report
    context["period_start"] = (today + timedelta(days=1)).isoformat()
    context["period_end"] = (today + timedelta(days=int(days))).isoformat()
    context["available_days"] = weekday_mode
    context["birth_date"] = user.birth_date
    report = await generate_paid_report(
        session, user.id, "date_selection", "date_selection", f"Подбор дат: {event_name}",
        context, DATE_SELECTION_PROMPT(lang), lang, max_tokens=2400,
        metadata={"event": event_type, "event_name": event_name,
                  "period_start": context["period_start"], "period_end": context["period_end"]})
    response = report.content

    dates_list = "\n".join(
        f"• {d['date']} ({d['weekday']}) — энергия {d['energy']}" for d in favorable
    )
    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    _hdr = {"ru": "Благоприятные даты для", "en": "Favorable dates for", "fa": "تاریخ‌های مناسب برای", "tr": "Uygun tarihler:"}.get(lang, "Favorable dates for")
    _ev_label = {"ru": "Событие", "en": "Event", "fa": "رویداد", "tr": "Etkinlik"}.get(lang, "Event")
    header = f"📆 {_hdr} — {name}\n{_ev_label}: {event_name}\n\n{dates_list}\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Выбрать другое событие", callback_data="menu:dates")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])
    await safe_edit_ai(thinking_msg, header + response, reply_markup=kb)
    await callback.answer()
