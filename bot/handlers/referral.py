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


def _build_referral_text(stats: dict, link: str, lang: str = "ru") -> str:
    _title   = {"ru": "👥 Раздел «Друзья»",   "en": "👥 Friends",           "fa": "👥 بخش دوستان",       "tr": "👥 Arkadaşlar"}.get(lang, "👥 Friends")
    _desc    = {"ru": "Приглашай друзей и получай бонусные дни к подписке.",
                "en": "Invite friends and earn bonus days for your subscription.",
                "fa": "دوستان را دعوت کنید و روزهای جایزه برای اشتراکتان دریافت کنید.",
                "tr": "Arkadaşlarınızı davet edin ve aboneliğinize bonus günler kazanın."}.get(lang, "Invite friends and earn bonus days for your subscription.")
    _bonus   = {"ru": f"ты получишь *+1 день* к своей подписке",
                "en": f"you will receive *+1 day* to your subscription",
                "fa": f"*۱ روز* به اشتراک شما اضافه می‌شود",
                "tr": f"aboneliğinize *+1 gün* eklenecektir"}.get(lang, "you will receive *+1 day* to your subscription")
    _cond    = {"ru": "Если друг зарегистрируется по твоей ссылке и оформит любой тариф —",
                "en": "If a friend registers via your link and purchases any plan —",
                "fa": "اگر دوستی از طریق لینک شما ثبت‌نام کند و هر طرحی بخرد —",
                "tr": "Bir arkadaşınız bağlantınız aracılığıyla kayıt olur ve herhangi bir plan satın alırsa —"}.get(lang, "If a friend registers via your link and purchases any plan —")
    _invited = {"ru": "Приглашено друзей", "en": "Friends invited", "fa": "دوستان دعوت شده", "tr": "Davet edilen arkadaşlar"}.get(lang, "Friends invited")
    _bonuses = {"ru": "Активировано бонусов", "en": "Bonuses activated", "fa": "جوایز فعال شده", "tr": "Etkinleştirilen bonuslar"}.get(lang, "Bonuses activated")
    _days    = {"ru": "дней", "en": "days", "fa": "روز", "tr": "gün"}.get(lang, "days")
    _link_l  = {"ru": "Твоя ссылка", "en": "Your link", "fa": "لینک شما", "tr": "Bağlantınız"}.get(lang, "Your link")

    return (
        f"*{_title}*\n\n"
        f"{_desc}\n\n"
        f"{_cond} {_bonus}.\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 {_invited}: *{stats['total']}*\n"
        f"💎 {_bonuses}: *+{stats['bonus_days']} {_days}*\n\n"
        f"━━━━━━━━━━━━━━━\n"
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
    _title   = {"ru": "📊 Твоя статистика",   "en": "📊 Your statistics",  "fa": "📊 آمار شما",         "tr": "📊 İstatistikleriniz"}.get(lang, "📊 Your statistics")
    _invited = {"ru": "Приглашено",            "en": "Invited",             "fa": "دعوت شده",            "tr": "Davet edilen"}.get(lang, "Invited")
    _active  = {"ru": "Активных рефералов",    "en": "Active referrals",    "fa": "ارجاع‌های فعال",     "tr": "Aktif yönlendirmeler"}.get(lang, "Active referrals")
    _bonuses = {"ru": "Получено бонусов",      "en": "Bonuses received",    "fa": "جوایز دریافتی",       "tr": "Alınan bonuslar"}.get(lang, "Bonuses received")
    _days    = {"ru": "дней",                  "en": "days",                "fa": "روز",                 "tr": "gün"}.get(lang, "days")
    _note1   = {"ru": "Бонусные дни начисляются автоматически после первой оплаты приглашённого.",
                "en": "Bonus days are credited automatically after the first payment of the invited person.",
                "fa": "روزهای جایزه به طور خودکار پس از اولین پرداخت دعوت‌شده اضافه می‌شوند.",
                "tr": "Bonus günler, davet edilen kişinin ilk ödemesinden sonra otomatik olarak eklenir."}.get(lang, "Bonus days are credited automatically after the first payment of the invited person.")
    _note2   = {"ru": "Если у вас нет активной подписки — дни сохранятся и применятся при следующей покупке.",
                "en": "If you don't have an active subscription — days will be saved and applied on your next purchase.",
                "fa": "اگر اشتراک فعال ندارید — روزها ذخیره می‌شوند و در خرید بعدی اعمال می‌شوند.",
                "tr": "Aktif bir aboneliğiniz yoksa — günler kaydedilir ve bir sonraki satın alımınızda uygulanır."}.get(lang, "If you don't have an active subscription — days will be saved and applied on your next purchase.")

    text = (
        f"*{_title}*\n\n"
        f"👥 {_invited}: *{stats['total']}*\n"
        f"💎 {_active}: *{stats['paid']}*\n"
        f"✨ {_bonuses}: *+{stats['bonus_days']} {_days}*\n\n"
        f"_{_note1}_\n"
        f"_{_note2}_"
    )
    await callback.message.edit_text(text, reply_markup=_stats_kb(lang), parse_mode="Markdown")
    await callback.answer()
