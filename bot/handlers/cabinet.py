"""Личный кабинет пользователя — «💎 Подписка»."""
import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import User, UserProfile, Subscription, SubscriptionStatusEnum, PlanEnum
from bot.services.limits import get_user_plan, get_limits_summary
from bot.keyboards.main import plans_keyboard

router = Router()
logger = logging.getLogger(__name__)


# ─── Шаблоны описания личности ────────────────────────────────────────────────

PERSONALITY_TEMPLATES = [
    (
        "🌙 Вы относитесь к людям с сильной внутренней чувствительностью.\n\n"
        "Вы часто замечаете детали, которые другие игнорируют.\n\n"
        "Иногда вам требуется время, чтобы принять решение, но интуиция редко подводит вас."
    ),
    (
        "✨ У вас развитая интуиция и способность чувствовать энергетику людей вокруг.\n\n"
        "Вы цените глубокие связи и ищете смысл в происходящих событиях.\n\n"
        "В периоды перемен ваша чуткость становится особенно сильной."
    ),
    (
        "🔮 Вы обладаете аналитическим умом, но часто руководствуетесь внутренним чутьём.\n\n"
        "Окружающие ценят вашу способность видеть суть вещей.\n\n"
        "Вы из тех, кто принимает решения осознанно — но не без участия интуиции."
    ),
    (
        "🌟 Вы человек, который чувствует перемены ещё до того, как они происходят.\n\n"
        "Эта чувствительность — ваша сила, а не слабость.\n\n"
        "Внутренний голос подсказывает вам верное направление в нужный момент."
    ),
    (
        "🌙 В вас сочетаются сила и мягкость.\n\n"
        "Вы способны глубоко чувствовать, при этом сохраняя внутренний стержень.\n\n"
        "Именно это привлекает к вам людей, которые ищут поддержку и понимание."
    ),
]


async def _get_or_create_personality(session: AsyncSession, user_id: int) -> str:
    """Вернуть сохранённое описание или сгенерировать и сохранить новое."""
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return random.choice(PERSONALITY_TEMPLATES)

    prefs = dict(profile.preferences or {})
    if "personality" in prefs:
        return prefs["personality"]

    # Генерируем и сохраняем (детерминировано по user_id для консистентности)
    personality = PERSONALITY_TEMPLATES[user_id % len(PERSONALITY_TEMPLATES)]
    prefs["personality"] = personality
    profile.preferences = prefs
    await session.commit()
    return personality


# ─── Форматирование лимитов ───────────────────────────────────────────────────

LIMIT_LABELS = {
    "ai_messages":        "AI‑сообщений",
    "personal_questions": "Личных вопросов",
    "weekly_reports":     "Недельных раскладов",
    "compatibility":      "Совместимостей",
    "daily_forecasts":    "Ежедневных прогнозов",
    "mini_readings":      "Мини‑разборов",
    "date_selections":    "Подборов дат",
    "tarot_cards":        "Карт дня",
}

PLAN_LABELS = {
    "free":    "Бесплатный",
    "lite":    "💫 Lite",
    "premium": "🌟 Premium",
    "pro":     "🔥 Pro",
}


async def _build_cabinet_text(session: AsyncSession, user: User) -> str:
    plan = await get_user_plan(session, user.id)
    plan_label = PLAN_LABELS.get(plan, plan)

    # Дата окончания
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    expires_str = "—"
    if sub and sub.expires_at:
        if sub.status == SubscriptionStatusEnum.active:
            expires_str = sub.expires_at.strftime("%d.%m.%Y")
        else:
            expires_str = "Истекла"

    # Лимиты
    limits = await get_limits_summary(session, user.id)
    personality = await _get_or_create_personality(session, user.id)

    name = user.first_name or "друг"

    lines_limits = []
    for key, label in LIMIT_LABELS.items():
        info = limits.get(key, {})
        remaining = info.get("remaining", 0)
        max_val = info.get("max", 0)
        if max_val > 0:
            lines_limits.append(f"• {label}: *{remaining}* из {max_val}")

    limits_block = "\n".join(lines_limits) if lines_limits else "• Лимиты недоступны на бесплатном тарифе"

    # Лейбл блока лимитов: для бесплатного — "всего", для платных — "за период"
    limits_label = "📊 *Остаток (всего):*" if plan == "free" else "📊 *Остаток за период:*"

    text = (
        f"✨ *Персональное пространство — {name}*\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *Тариф:* {plan_label}\n"
        f"📅 *Активен до:* {expires_str}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{limits_label}\n"
        f"{limits_block}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{personality}"
    )
    return text


def _cabinet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Продлить / сменить тариф", callback_data="menu:plans")],
        [InlineKeyboardButton(text="📋 Все тарифы", callback_data="menu:plans")],
        [InlineKeyboardButton(text="🔮 Главное меню", callback_data="menu:main")],
    ])


# ─── Обработчики ─────────────────────────────────────────────────────────────

@router.message(F.text == "💎 Подписка")
async def reply_cabinet(message: Message, user: User, session: AsyncSession, state: FSMContext):
    t0 = time.monotonic()
    logger.info("MENU_HANDLER_STARTED handler=reply_cabinet user=%s", message.from_user.id)
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    from bot.utils import show_menu_message
    text = await _build_cabinet_text(session, user)
    await show_menu_message(message, user.telegram_id, text, _cabinet_kb(), force_new=True, fast=True)
    logger.info("MENU_RENDER_DONE handler=reply_cabinet duration_ms=%.0f", (time.monotonic() - t0) * 1000)


@router.callback_query(F.data == "cabinet:open")
async def cb_cabinet_open(callback: CallbackQuery, user: User, session: AsyncSession):
    text = await _build_cabinet_text(session, user)
    try:
        await callback.message.edit_text(text, reply_markup=_cabinet_kb(), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=_cabinet_kb(), parse_mode="Markdown")
    await callback.answer()
