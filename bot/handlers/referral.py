"""Реферальная система — раздел «👥 Друзья»."""
import asyncio
import logging
import time
from urllib.parse import quote
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from bot.models.user import User, Referral

router = Router()
logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ref_link(bot_username: str, telegram_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{telegram_id}"


async def _get_stats(session: AsyncSession, telegram_id: int) -> dict:
    """Считает статистику по рефералам пользователя."""
    # Всего приглашено
    total_res = await session.execute(
        select(func.count()).where(Referral.inviter_telegram_id == telegram_id)
    )
    total = total_res.scalar() or 0

    # Оплатили (purchase_status=True)
    paid_res = await session.execute(
        select(func.count()).where(
            Referral.inviter_telegram_id == telegram_id,
            Referral.purchase_status == True,   # noqa: E712
        )
    )
    paid = paid_res.scalar() or 0

    # Бонусных дней выдано (reward_given=True)
    bonus_res = await session.execute(
        select(func.count()).where(
            Referral.inviter_telegram_id == telegram_id,
            Referral.reward_given == True,       # noqa: E712
        )
    )
    bonus_days = bonus_res.scalar() or 0

    return {"total": total, "paid": paid, "bonus_days": bonus_days}


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

_REFERRAL_INVITE_TEXT: dict[str, str] = {
    "ru": "\n✨ Запусти бота потомственной хранительницы знаний бабушки Aisha — и получи 8 бесплатных анализов по своей дате рождения.",
    "en": "\n✨ Start the bot of hereditary knowledge keeper Grandma Aisha — and get 8 free analyses based on your date of birth.",
    "fa": "\n✨ ربات بابا آیشا، نگهبان موروثی دانش را راه‌اندازی کنید — و ۸ تحلیل رایگان بر اساس تاریخ تولد خود دریافت کنید.",
    "tr": "\n✨ Geleneksel bilgi koruyucusu Büyükanne Aisha'nın botunu başlatın — ve doğum tarihinize göre 8 ücretsiz analiz alın.",
}


REFERRAL_LEVELS = [
    (1,  "🌱 Новичок",     [("personal_question", 1)]),
    (3,  "⭐ Активный",    [("tarot_card", 1), ("mini_reading", 1)]),
    (5,  "🔥 Продвинутый", [("compatibility", 1), ("weekly_report", 1)]),
    (10, "💎 Мастер",      [("full_matrix", 1), ("personal_question", 2)]),
    (20, "👑 Легенда",     [("vip_days", 3)]),
]


def _get_level(total: int) -> tuple[str, str]:
    """Вернуть (эмоджи+имя, следующий порог) по числу рефералов."""
    level_name = "🌑 Начало"
    for threshold, name, _ in REFERRAL_LEVELS:
        if total >= threshold:
            level_name = name
    next_threshold = None
    for threshold, _, _ in REFERRAL_LEVELS:
        if total < threshold:
            next_threshold = threshold
            break
    return level_name, next_threshold


def _build_referral_text(stats: dict, link: str, lang: str = "ru") -> str:
    total = stats["total"]
    level_name, next_threshold = _get_level(total)

    _link_l = {"ru": "Твоя ссылка", "en": "Your link", "fa": "لینک شما", "tr": "Bağlantınız"}.get(lang, "Your link")
    _next = ""
    if next_threshold:
        _next = f"\n🎯 До следующего уровня: *{next_threshold - total}* друзей"

    return (
        f"*👥 Раздел «Друзья»*\n\n"
        f"Приглашай друзей — получай бесплатный доступ к разделам!\n\n"
        f"Чем больше друзей — тем больше подарков:\n\n"
        f"🌱 1 друг → Личный вопрос\n"
        f"⭐ 3 друга → Карта дня + Мини-разбор\n"
        f"🔥 5 друзей → Совместимость + Расклад на неделю\n"
        f"💎 10 друзей → Матрица судьбы + 2 Личных вопроса\n"
        f"👑 20 друзей → 3 дня VIP (полный доступ)\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено друзей: *{total}*\n"
        f"🏆 Уровень: *{level_name}*"
        f"{_next}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🔗 {_link_l}:\n`{link}`"
    )


def _referral_kb(invite_url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    invite_text = _REFERRAL_INVITE_TEXT.get(lang, _REFERRAL_INVITE_TEXT["en"])
    share_url = f"https://t.me/share/url?url={quote(invite_url)}&text={quote(invite_text)}"
    _invite  = {"ru": "📨 Пригласить друга", "en": "📨 Invite a friend", "fa": "📨 دعوت دوست", "tr": "📨 Arkadaş davet et"}.get(lang, "📨 Invite a friend")
    _stats_b = {"ru": "📊 Моя статистика",  "en": "📊 My statistics",  "fa": "📊 آمار من",    "tr": "📊 İstatistiklerim"}.get(lang, "📊 My statistics")
    _menu    = {"ru": "🔮 Главное меню",     "en": "🔮 Main menu",      "fa": "🔮 منوی اصلی",  "tr": "🔮 Ana menü"}.get(lang, "🔮 Main menu")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_invite,  url=share_url)],
        [InlineKeyboardButton(text=_stats_b, callback_data="referral:stats")],
        [InlineKeyboardButton(text=_menu,    callback_data="menu:main")],
    ])


def _stats_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    _back = {"ru": "◀️ Назад", "en": "◀️ Back", "fa": "◀️ بازگشت", "tr": "◀️ Geri"}.get(lang, "◀️ Back")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_back, callback_data="referral:back")],
    ])


# ─── Обработчики ─────────────────────────────────────────────────────────────

@router.message(F.text.in_({"👥 Друзья", "👥 Friends", "👥 دوستان", "👥 Arkadaşlar"}))
async def reply_friends(message: Message, user: User, session: AsyncSession, state: FSMContext, lang: str = "ru"):
    t0 = time.monotonic()
    logger.info("MENU_HANDLER_STARTED handler=reply_friends user=%s", message.from_user.id)
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    from bot.utils import show_menu_message
    from bot.handlers.share import _get_bot_username
    bot_username = await _get_bot_username(message.bot)
    link = _ref_link(bot_username, user.telegram_id)
    stats = await _get_stats(session, user.telegram_id)
    text = _build_referral_text(stats, link, lang)
    await show_menu_message(message, user.telegram_id, text, _referral_kb(link, lang), force_new=True, fast=True)
    logger.info("MENU_RENDER_DONE handler=reply_friends duration_ms=%.0f", (time.monotonic() - t0) * 1000)


@router.callback_query(F.data == "referral:back")
async def referral_back(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.handlers.share import _get_bot_username
    bot_username = await _get_bot_username(callback.bot)
    link = _ref_link(bot_username, user.telegram_id)
    stats = await _get_stats(session, user.telegram_id)
    text = _build_referral_text(stats, link, lang)
    try:
        await callback.message.edit_text(text, reply_markup=_referral_kb(link, lang), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=_referral_kb(link, lang), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "referral:stats")
async def referral_stats(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    stats = await _get_stats(session, user.telegram_id)
    total = stats["total"]
    level_name, next_threshold = _get_level(total)

    # Показать какие уровни получены
    lines = []
    for threshold, name, rewards in REFERRAL_LEVELS:
        check = "✅" if total >= threshold else "⬜"
        lines.append(f"{check} {name} ({threshold} друзей)")

    levels_block = "\n".join(lines)
    _next = ""
    if next_threshold:
        _next = f"\n\n🎯 До следующего уровня: *{next_threshold - total}* друзей"

    text = (
        f"*📊 Твоя статистика*\n\n"
        f"👥 Приглашено: *{total}*\n"
        f"🏆 Уровень: *{level_name}*\n\n"
        f"*Прогресс по уровням:*\n{levels_block}"
        f"{_next}"
    )
    await callback.message.edit_text(text, reply_markup=_stats_kb(lang), parse_mode="Markdown")
    await callback.answer()
