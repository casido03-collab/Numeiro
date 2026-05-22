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
from bot.services.ai_service import generate
from bot.prompts.prompts import WEEKLY_PREDICTION_PROMPT
from bot.keyboards.main import sphere_menu, limit_reached_keyboard, back_to_main

router = Router()

SPHERE_NAMES = {
    "love": "любовь и отношения",
    "money": "деньги и финансы",
    "work": "работа и карьера",
    "health": "здоровье и энергия",
    "family": "семья",
    "decision": "важные решения",
    "general": "общий прогноз",
}

WEEKDAY_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


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
async def weekly_start(callback: CallbackQuery, user: User, session: AsyncSession):
    has_limit, used, max_val = await check_limit(session, user.id, "weekly_reports")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Расклад на неделю*\n\nЭта функция требует подписки или разовой покупки.\n\n"
            "• Lite: недельные расклады не включены\n"
            "• Premium: 2 расклада в месяц\n"
            "• Pro: 4 расклада в месяц",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            "✨ Для расклада мне нужна твоя дата рождения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📅 *Расклад на неделю*\n\nВыбери сферу для прогноза:",
        reply_markup=sphere_menu("weekly_sphere", back="menu:main"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("weekly_sphere:"))
async def weekly_sphere_selected(callback: CallbackQuery, user: User, session: AsyncSession):
    sphere = callback.data.split(":")[-1]

    thinking_msg = await callback.message.edit_text("🔮 Формирую прогноз на ближайшие дни...")

    today = date.today()
    week_start = today
    week_end = today + timedelta(days=6)

    birth_date_obj = parse_birth_date(user.birth_date)
    if not birth_date_obj:
        await thinking_msg.edit_text("❌ Дата рождения не найдена.")
        await callback.answer()
        return

    cache_key = make_cache_key("weekly", user.birth_date, sphere, week_start.strftime("%Y-%W"))
    cached = await get_cached(cache_key)

    if not cached:
        nums = calculate_all(birth_date_obj)
        week_nums = _week_energy(birth_date_obj, week_start)
        days = []
        for i in range(7):
            d = today + timedelta(days=i)
            days.append({
                "date": d.strftime("%d.%m"),
                "weekday": WEEKDAY_RU[d.weekday()],
            })
        context = {
            "name": user.first_name or "друг",
            "birth_date": user.birth_date,
            "sphere": SPHERE_NAMES.get(sphere, sphere),
            "week_start": week_start.strftime("%d.%m.%Y"),
            "week_end": week_end.strftime("%d.%m.%Y"),
            "days": days,
            "numbers": nums,
            "week_energy": week_nums,
        }
        user_msg = (
            f"Создай недельный прогноз для сферы '{SPHERE_NAMES.get(sphere, sphere)}'.\n"
            f"Данные: {json.dumps(context, ensure_ascii=False)}"
        )
        cached = await generate(
            session, user.id, "weekly_report",
            WEEKLY_PREDICTION_PROMPT, user_msg,
            complexity="medium", max_tokens=700,
        )
        await set_cached(cache_key, cached, ttl=3600 * 24 * 7)

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "weekly_forecast",
        title=f"Прогноз {week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m')} | {SPHERE_NAMES.get(sphere, sphere)}",
        content=cached,
        metadata={"sphere": sphere, "week_start": str(week_start), "week_end": str(week_end)},
    )
    await consume_limit(session, user.id, "weekly_reports")
    await consume_limit(session, user.id, "ai_messages")

    name = user.first_name or "друг"
    sphere_name = SPHERE_NAMES.get(sphere, sphere)
    header = (
        f"📅 *Прогноз на неделю — {name}*\n"
        f"_{week_start.strftime('%d.%m')} — {week_end.strftime('%d.%m.%Y')}_\n"
        f"Сфера: *{sphere_name}*\n\n"
    )
    from bot.keyboards.main import after_reading_keyboard_weekly
    await safe_edit_ai(thinking_msg, header + cached, reply_markup=after_reading_keyboard_weekly())
    await callback.answer()
