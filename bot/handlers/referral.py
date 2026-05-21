"""Реферальная система — раздел «👥 Друзья»."""
import logging
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

_REFERRAL_TEXT = (
    "\n✨ Запусти бота потомственной хранительницы знаний бабушки Aisha — "
    "и получи 8 бесплатных анализов по своей дате рождения."
)


def _referral_kb(invite_url: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(invite_url)}&text={quote(_REFERRAL_TEXT)}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Пригласить друга", url=share_url)],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="referral:stats")],
        [InlineKeyboardButton(text="🔮 Главное меню", callback_data="menu:main")],
    ])


def _stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="referral:back")],
    ])


# ─── Обработчики ─────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Друзья")
async def reply_friends(message: Message, user: User, session: AsyncSession, state: FSMContext):
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    from bot.utils import show_menu_message
    bot_username = (await message.bot.get_me()).username
    link = _ref_link(bot_username, user.telegram_id)
    stats = await _get_stats(session, user.telegram_id)
    text = (
        f"👥 *Раздел «Друзья»*\n\n"
        f"Приглашай друзей и получай бонусные дни к подписке.\n\n"
        f"Если друг зарегистрируется по твоей ссылке и оформит любой тариф — "
        f"ты получишь *+1 день* к своей подписке.\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено друзей: *{stats['total']}*\n"
        f"💎 Активировано бонусов: *+{stats['bonus_days']} дней*\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 Твоя ссылка:\n`{link}`"
    )
    await show_menu_message(message, user.telegram_id, text, _referral_kb(link))


@router.callback_query(F.data == "referral:back")
async def referral_back(callback: CallbackQuery, user: User, session: AsyncSession):
    bot_username = (await callback.bot.get_me()).username
    link = _ref_link(bot_username, user.telegram_id)

    stats = await _get_stats(session, user.telegram_id)

    text = (
        f"👥 *Раздел «Друзья»*\n\n"
        f"Приглашай друзей и получай бонусные дни к подписке.\n\n"
        f"Если друг зарегистрируется по твоей ссылке и оформит любой тариф — "
        f"ты получишь *+1 день* к своей подписке.\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено друзей: *{stats['total']}*\n"
        f"💎 Активировано бонусов: *+{stats['bonus_days']} дней*\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 Твоя ссылка:\n`{link}`"
    )
    try:
        await callback.message.edit_text(text, reply_markup=_referral_kb(link), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=_referral_kb(link), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "referral:stats")
async def referral_stats(callback: CallbackQuery, user: User, session: AsyncSession):
    stats = await _get_stats(session, user.telegram_id)

    text = (
        f"📊 *Твоя статистика*\n\n"
        f"👥 Приглашено: *{stats['total']}*\n"
        f"💎 Активных рефералов: *{stats['paid']}*\n"
        f"✨ Получено бонусов: *+{stats['bonus_days']} дней*\n\n"
        f"_Бонусные дни начисляются автоматически после первой оплаты приглашённого._\n"
        f"_Если у тебя нет активной подписки — дни сохранятся и применятся при следующей покупке._"
    )
    await callback.message.edit_text(text, reply_markup=_stats_kb(), parse_mode="Markdown")
    await callback.answer()
