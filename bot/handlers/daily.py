"""Ежедневный прогноз."""
import json
from datetime import date, datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import User
from bot.services.numerology import calculate_all, _reduce
from bot.services.cache import get_cached, set_cached, make_cache_key, get_redis
from bot.services.limits import check_limit, consume_limit, get_user_plan
from bot.services.ai_service import generate
from bot.prompts.prompts import DAILY_FORECAST_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import back_to_main, limit_reached_keyboard
from bot.utils import parse_birth_date, safe_edit, safe_edit_ai
from bot.services.thinking import random_thinking
from config import PLANS

router = Router()

_WEEKDAY_NAMES: dict[str, list[str]] = {
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "fa": ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"],
    "tr": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
}

_FRIEND: dict[str, str] = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}


def _day_number(birth_date: date, target: date) -> int:
    day_sum = target.day + target.month + sum(int(c) for c in str(target.year))
    personal = birth_date.day + birth_date.month
    return _reduce(day_sum + personal)


async def _check_energy_total(user_id: int, plan: str) -> tuple[bool, int, int]:
    """
    Check Redis total energy counter for Lite/Pro plans.
    Returns (ok, used, max_total). max_total=0 means no total limit.
    """
    plan_config = PLANS.get(plan, {})
    max_total = plan_config.get("energy_day_total")
    if max_total is None:
        return True, 0, 0  # No total cap (Premium, Free)

    r = await get_redis()
    val = await r.get(f"nrg_total:{user_id}")
    used = int(val) if val else 0
    return used < max_total, used, max_total


async def _consume_energy_total(user_id: int, plan: str, session: AsyncSession) -> None:
    """Increment Redis total energy counter; set TTL on first use from subscription expiry."""
    plan_config = PLANS.get(plan, {})
    if plan_config.get("energy_day_total") is None:
        return  # No total cap for this plan

    from bot.models.user import Subscription
    r = await get_redis()
    key = f"nrg_total:{user_id}"
    new_val = await r.incr(key)

    if new_val == 1:
        # First use — set TTL to subscription expiry or plan default
        result = await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()
        if sub and sub.expires_at:
            ttl = int((sub.expires_at - datetime.now(timezone.utc)).total_seconds())
            if ttl > 0:
                await r.expire(key, ttl)
                return
        # Fallback TTL
        days = 7 if plan == "lite" else 30
        await r.expire(key, days * 24 * 3600)


@router.callback_query(F.data == "menu:daily")
async def daily_forecast(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    plan = await get_user_plan(session, user.id)

    # ── 1. Daily cap (1/day for all plans including free) ─────────────────────
    has_daily, used_daily, max_daily = await check_limit(session, user.id, "daily_forecasts")

    _title = {"ru": "Энергия дня", "en": "Daily Energy", "fa": "انرژی روز", "tr": "Günün Enerjisi"}.get(lang, "Daily Energy")
    if not has_daily:
        _already = {
            "ru": f"⚡ *{_title}*\n\n✨ Вы уже получили энергию дня сегодня.\nВозвращайтесь завтра за новым прогнозом! 🌙",
            "en": f"⚡ *{_title}*\n\n✨ You have already received today's energy.\nCome back tomorrow for a new forecast! 🌙",
            "fa": f"⚡ *{_title}*\n\n✨ شما امروز انرژی روز را دریافت کرده‌اید.\nفردا برای پیش‌بینی جدید برگردید! 🌙",
            "tr": f"⚡ *{_title}*\n\n✨ Bugünün enerjisini zaten aldınız.\nYeni tahmin için yarın gelin! 🌙",
        }.get(lang, f"⚡ *{_title}*\n\n✨ You have already received today's energy.\nCome back tomorrow! 🌙")
        await callback.message.edit_text(_already, reply_markup=limit_reached_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    # ── 2. Total cap for Lite (3 total) and Pro (30 total) ────────────────────
    ok_total, used_total, max_total = await _check_energy_total(user.id, plan)
    if not ok_total:
        plan_name = {"lite": "Lite", "pro": "Pro"}.get(plan, plan)
        _used_all = {
            "ru": (f"⚡ *{_title}*\n\n🔒 Вы использовали все {max_total} "
                   f"{'прогноза' if max_total < 5 else 'прогнозов'} по тарифу *{plan_name}*.\n\nОбновите подписку для продолжения."),
            "en": f"⚡ *{_title}*\n\n🔒 You have used all {max_total} forecasts on the *{plan_name}* plan.\n\nUpgrade your subscription to continue.",
            "fa": f"⚡ *{_title}*\n\n🔒 شما همه {max_total} پیش‌بینی طرح *{plan_name}* را استفاده کرده‌اید.\n\nبرای ادامه اشتراک خود را ارتقاء دهید.",
            "tr": f"⚡ *{_title}*\n\n🔒 *{plan_name}* planındaki {max_total} tahminini kullandınız.\n\nDevam etmek için aboneliğinizi yükseltin.",
        }.get(lang, f"⚡ *{_title}*\n\n🔒 All {max_total} forecasts used on *{plan_name}* plan.")
        await callback.message.edit_text(_used_all, reply_markup=limit_reached_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    # ── 3. Birth date required ────────────────────────────────────────────────
    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        _no_dob = {
            "ru": "✨ Для прогноза нужна дата рождения.\n\nВведите её — и я сразу верну вас сюда.",
            "en": "✨ A birth date is needed for the forecast.\n\nEnter it — and I'll bring you right back here.",
            "fa": "✨ برای پیش‌بینی به تاریخ تولد نیاز است.\n\nآن را وارد کنید — و بلافاصله اینجا برمی‌گردید.",
            "tr": "✨ Tahmin için doğum tarihiniz gerekiyor.\n\nGirin — ve hemen buraya geri döneceğim.",
        }.get(lang, "✨ A birth date is needed for the forecast.")
        _enter = {"ru": "✨ Ввести дату рождения", "en": "✨ Enter birth date",
                  "fa": "✨ تاریخ تولد را وارد کنید", "tr": "✨ Doğum tarihi gir"}.get(lang, "✨ Enter birth date")
        _back = {"ru": "◀️ Назад", "en": "◀️ Back", "fa": "◀️ بازگشت", "tr": "◀️ Geri"}.get(lang, "◀️ Back")
        await callback.message.edit_text(
            _no_dob,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_enter, callback_data="birth_date:collect:menu:daily")],
                [InlineKeyboardButton(text=_back, callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    thinking_msg = await callback.message.edit_text(random_thinking())

    today = date.today()
    birth_date_obj = parse_birth_date(user.birth_date)

    if not birth_date_obj:
        _err = {"ru": "❌ Ошибка: дата рождения не найдена.", "en": "❌ Error: birth date not found.",
                "fa": "❌ خطا: تاریخ تولد یافت نشد.", "tr": "❌ Hata: doğum tarihi bulunamadı."}.get(lang, "❌ Error: birth date not found.")
        await thinking_msg.edit_text(_err)
        await callback.answer()
        return

    # ── 4. Cache by birth_date + date (shared across users with same DOB) ─────
    cache_key = make_cache_key("daily", user.birth_date, today.strftime("%Y-%m-%d"))
    cached = await get_cached(cache_key)

    if not cached:
        day_num = _day_number(birth_date_obj, today)
        nums = calculate_all(birth_date_obj)
        weekday_name = (_WEEKDAY_NAMES.get(lang) or _WEEKDAY_NAMES["en"])[today.weekday()]
        context = {
            "name": user.first_name or _FRIEND.get(lang, "friend"),
            "date": today.strftime("%d.%m.%Y"),
            "weekday": weekday_name,
            "day_number": day_num,
            "numbers": {k: v for k, v in nums.items() if k in ["life_path", "destiny", "personality"]},
        }
        user_msg = f"Создай ежедневный прогноз.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(
            session, user.id, "daily_forecast",
            DAILY_FORECAST_PROMPT(lang), user_msg,
            complexity="simple", max_tokens=300,
        )
        await set_cached(cache_key, cached, ttl=3600 * 20)

    from bot.services.reports_service import save_report
    _save_title = {"ru": "Энергия дня", "en": "Daily Energy", "fa": "انرژی روز", "tr": "Günün Enerjisi"}.get(lang, "Daily Energy")
    await save_report(
        session, user.id, "daily_energy",
        title=f"{_save_title} {today.strftime('%d.%m.%Y')}",
        content=cached,
        metadata={"date": today.isoformat()},
    )

    # ── 5. Consume limits ─────────────────────────────────────────────────────
    await consume_limit(session, user.id, "daily_forecasts")
    await consume_limit(session, user.id, "ai_messages")
    await _consume_energy_total(user.id, plan, session)

    # ── 6. Send result ────────────────────────────────────────────────────────
    name = user.first_name or _FRIEND.get(lang, "friend")
    weekday_name = (_WEEKDAY_NAMES.get(lang) or _WEEKDAY_NAMES["en"])[today.weekday()]
    _energy_title = {"ru": "Энергия дня", "en": "Energy of the day", "fa": "انرژی روز", "tr": "Günün enerjisi"}.get(lang, "Energy of the day")
    header = f"⚡ *{_energy_title} — {name}*\n_{weekday_name}, {today.strftime('%d.%m.%Y')}_\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("menu_weekly", lang), callback_data="weekly:start")],
        [InlineKeyboardButton(text=t("menu_question", lang), callback_data="menu:question")],
        [InlineKeyboardButton(text=t("btn_back_to_main", lang), callback_data="menu:main")],
    ])
    await safe_edit_ai(thinking_msg, header + cached, reply_markup=kb)
    await callback.answer()
