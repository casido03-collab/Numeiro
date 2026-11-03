from bot.services.catalog import product_offer
from bot.services.limits import has_credit as product_has_credit
"""Недельный расклад."""
import json
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.numerology import calculate_all, _reduce
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.utils import parse_birth_date, safe_edit_ai
from bot.services.thinking import random_thinking
from bot.services.ai_service import generate
from bot.prompts.prompts import WEEKLY_PREDICTION_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import sphere_menu, limit_reached_keyboard, back_to_main

router = Router()

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
    translated = t(f"sphere_{sphere}", lang)
    if translated == f"sphere_{sphere}":
        return SPHERE_NAMES.get(sphere, sphere)
    return translated

WEEKDAY_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

_WEEKDAY_NAMES: dict[str, list[str]] = {
    "ru": WEEKDAY_RU,
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "fa": ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"],
    "tr": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
}

_FRIEND: dict[str, str] = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}


def _week_energy(birth_date: date, week_start: date) -> dict:
    """Calculate personal numbers for the week."""
    personal_year = _reduce(birth_date.day + birth_date.month + sum(int(c) for c in str(week_start.year)))
    personal_month = _reduce(birth_date.day + birth_date.month + week_start.month)
    week_number = week_start.isocalendar()[1]
    week_energy = _reduce(personal_year + week_number)
    return {
        "personal_year": personal_year,
        "personal_month": personal_month,
        "week_energy": week_energy,
        "week_number": week_number,
    }


@router.callback_query(F.data == "menu:weekly")
@router.callback_query(F.data == "weekly:start")
async def weekly_start(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.services.limits import has_credit, is_vip, check_vip_limit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    _is_vip = await is_vip(user.id)
    if not _is_vip and not await has_credit(user.id, "weekly_report"):
        _locked = product_offer("weekly_report", lang)
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("weekly_report", 79, 79, lang), parse_mode="Markdown")
        await callback.answer()
        return

    if _is_vip and not await check_vip_limit(user.id, "weekly_report") and not await product_has_credit(user.id, "weekly_report"):
        _exhausted = {
            "ru": "💎 Лимит VIP по этому разделу исчерпан на этот месяц.",
            "en": "💎 VIP limit for this section exhausted this month.",
            "fa": "💎 محدودیت VIP برای این بخش تمام شده.",
            "tr": "💎 Bu bölüm için VIP limitiniz doldu.",
        }.get(lang, "💎 VIP limit exhausted.")
        from bot.keyboards.main import back_to_main as _btm
        await callback.message.edit_text(_exhausted, reply_markup=_btm(), parse_mode="Markdown")
        await callback.answer()
        return

    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            "✨ Для расклада нам нужна ваша дата рождения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="birth_date:collect:menu:weekly")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    _prompt_text = {
        "ru": "📅 *Расклад на неделю*\n\nВыбери сферу для прогноза:",
        "en": "📅 *Weekly forecast*\n\nChoose a sphere for the forecast:",
        "fa": "📅 *پیش‌بینی هفتگی*\n\nیک حوزه برای پیش‌بینی انتخاب کن:",
        "tr": "📅 *Haftalık tahmin*\n\nTahmin için bir alan seçin:",
    }.get(lang, "📅 *Weekly forecast*\n\nChoose a sphere:")
    await callback.message.edit_text(
        _prompt_text,
        reply_markup=sphere_menu("weekly_sphere", back="menu:main"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("weekly_sphere:"))
async def weekly_sphere_selected(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    sphere = callback.data.split(":")[-1]

    thinking_msg = await callback.message.edit_text(random_thinking())

    today = date.today()
    week_start = today
    week_end = today + timedelta(days=6)

    birth_date_obj = parse_birth_date(user.birth_date)
    if not birth_date_obj:
        _err = {"ru": "❌ Дата рождения не найдена.", "en": "❌ Birth date not found.",
                "fa": "❌ تاریخ تولد یافت نشد.", "tr": "❌ Doğum tarihi bulunamadı."}.get(lang, "❌ Birth date not found.")
        await thinking_msg.edit_text(_err)
        await callback.answer()
        return

    from bot.services.fulfillment import generate_paid_report
    nums = calculate_all(birth_date_obj)
    week_nums = _week_energy(birth_date_obj, week_start)
    _wd_list = _WEEKDAY_NAMES.get(lang) or _WEEKDAY_NAMES["en"]
    days = []
    for i in range(7):
        d = today + timedelta(days=i)
        days.append({
            "date": d.strftime("%d.%m"),
            "weekday": _wd_list[d.weekday()],
        })
    sphere_label = _sphere(sphere, lang)
    context = {
        "name": user.first_name or _FRIEND.get(lang, "friend"),
        "birth_date": user.birth_date,
        "sphere": sphere_label,
        "week_start": week_start.strftime("%d.%m.%Y"),
        "week_end": week_end.strftime("%d.%m.%Y"),
        "days": days,
        "numbers": nums,
        "week_energy": week_nums,
    }
    report = await generate_paid_report(
        session, user.id, "weekly_report", "weekly_forecast",
        f"Прогноз {week_start:%d.%m}–{week_end:%d.%m} | {SPHERE_NAMES.get(sphere, sphere)}",
        context, WEEKLY_PREDICTION_PROMPT(lang), lang, max_tokens=3200,
        metadata={"sphere": sphere, "week_start": str(week_start), "week_end": str(week_end)})
    cached = report.content

    name = user.first_name or _FRIEND.get(lang, "friend")
    sphere_name = sphere_label
    _hdr_title = {"ru": "Прогноз на неделю", "en": "Weekly forecast", "fa": "پیش‌بینی هفتگی", "tr": "Haftalık tahmin"}.get(lang, "Weekly forecast")
    _hdr_sphere = {"ru": "Сфера", "en": "Sphere", "fa": "حوزه", "tr": "Alan"}.get(lang, "Sphere")
    header = (
        f"📅 {_hdr_title} — {name}\n"
        f"{week_start.strftime('%d.%m')} — {week_end.strftime('%d.%m.%Y')}\n"
        f"{_hdr_sphere}: {sphere_name}\n\n"
    )
    from bot.keyboards.main import after_reading_keyboard_weekly
    await safe_edit_ai(thinking_msg, header + cached, reply_markup=after_reading_keyboard_weekly())
    await callback.answer()
