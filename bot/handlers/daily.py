"""Ежедневный прогноз."""
import json
from datetime import date
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.numerology import calculate_all, _reduce
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.prompts.prompts import DAILY_FORECAST_PROMPT
from bot.keyboards.main import back_to_main, limit_reached_keyboard
from bot.utils import parse_birth_date, safe_edit

router = Router()


def _day_number(birth_date: date, target: date) -> int:
    day_sum = target.day + target.month + sum(int(c) for c in str(target.year))
    personal = birth_date.day + birth_date.month
    return _reduce(day_sum + personal)


@router.callback_query(F.data == "menu:daily")
async def daily_forecast(callback: CallbackQuery, user: User, session: AsyncSession):
    has_limit, used, max_val = await check_limit(session, user.id, "daily_forecasts")
    if not has_limit:
        await callback.message.edit_text(
            "🔒 *Ежедневный прогноз*\n\nЭта функция доступна в подписке.\n\n"
            "• Lite: 3 прогноза\n• Premium: 15 прогнозов\n• Pro: 45 прогнозов",
            reply_markup=limit_reached_keyboard(),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            "✨ Для прогноза мне нужна дата рождения.\n\nВведи дату через *«Мой разбор»* в главном меню.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Мой разбор", callback_data="free:start")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    thinking_msg = await callback.message.edit_text("⚡ Считываю энергию сегодняшнего дня...")

    today = date.today()
    birth_date_obj = parse_birth_date(user.birth_date)

    if not birth_date_obj:
        await thinking_msg.edit_text("❌ Ошибка: дата рождения не найдена.")
        await callback.answer()
        return

    cache_key = make_cache_key("daily", user.birth_date, today.strftime("%Y-%m-%d"))
    cached = await get_cached(cache_key)

    if not cached:
        day_num = _day_number(birth_date_obj, today)
        nums = calculate_all(birth_date_obj)
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        context = {
            "name": user.first_name or "друг",
            "date": today.strftime("%d.%m.%Y"),
            "weekday": weekday_names[today.weekday()],
            "day_number": day_num,
            "numbers": {k: v for k, v in nums.items() if k in ["life_path", "destiny", "personality"]},
        }
        user_msg = f"Создай ежедневный прогноз.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(
            session, user.id, "daily_forecast",
            DAILY_FORECAST_PROMPT, user_msg,
            complexity="simple", max_tokens=300,
        )
        await set_cached(cache_key, cached, ttl=3600 * 20)

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "daily_energy",
        title=f"Энергия дня {today.strftime('%d.%m.%Y')}",
        content=cached,
        metadata={"date": today.isoformat()},
    )
    await consume_limit(session, user.id, "daily_forecasts")
    await consume_limit(session, user.id, "ai_messages")

    name = user.first_name or "друг"
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    header = f"⚡ *Энергия дня — {name}*\n_{weekday_names[today.weekday()]}, {today.strftime('%d.%m.%Y')}_\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data="weekly:start")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu:question")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])
    await safe_edit(thinking_msg, header + cached, reply_markup=kb)
    await callback.answer()
