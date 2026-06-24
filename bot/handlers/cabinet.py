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
from bot.keyboards.main import back_to_main

router = Router()
logger = logging.getLogger(__name__)


# ─── Шаблоны описания личности ────────────────────────────────────────────────

PERSONALITY_TEMPLATES: dict[str, list[str]] = {
    "ru": [
        "🌙 Вы относитесь к людям с сильной внутренней чувствительностью.\n\nВы часто замечаете детали, которые другие игнорируют.\n\nИногда вам требуется время, чтобы принять решение, но интуиция редко подводит вас.",
        "✨ У вас развитая интуиция и способность чувствовать энергетику людей вокруг.\n\nВы цените глубокие связи и ищете смысл в происходящих событиях.\n\nВ периоды перемен ваша чуткость становится особенно сильной.",
        "🔮 Вы обладаете аналитическим умом, но часто руководствуетесь внутренним чутьём.\n\nОкружающие ценят вашу способность видеть суть вещей.\n\nВы из тех, кто принимает решения осознанно — но не без участия интуиции.",
        "🌟 Вы человек, который чувствует перемены ещё до того, как они происходят.\n\nЭта чувствительность — ваша сила, а не слабость.\n\nВнутренний голос подсказывает вам верное направление в нужный момент.",
        "🌙 В вас сочетаются сила и мягкость.\n\nВы способны глубоко чувствовать, при этом сохраняя внутренний стержень.\n\nИменно это привлекает к вам людей, которые ищут поддержку и понимание.",
    ],
    "en": [
        "🌙 You are someone with a strong inner sensitivity.\n\nYou often notice details that others overlook.\n\nSometimes you need time to make a decision, but your intuition rarely leads you astray.",
        "✨ You have a developed intuition and the ability to sense the energy of those around you.\n\nYou value deep connections and seek meaning in events.\n\nDuring times of change, your sensitivity becomes especially strong.",
        "🔮 You have an analytical mind, but often follow your inner instinct.\n\nThose around you appreciate your ability to see the essence of things.\n\nYou are one of those who makes decisions consciously — but never without intuition.",
        "🌟 You are someone who feels change before it happens.\n\nThis sensitivity is your strength, not a weakness.\n\nYour inner voice guides you in the right direction at the right moment.",
        "🌙 You combine strength and gentleness.\n\nYou are able to feel deeply while maintaining your inner core.\n\nThis is what attracts people to you who seek support and understanding.",
    ],
    "fa": [
        "🌙 شما از افرادی هستید که حساسیت درونی قوی دارند.\n\nشما اغلب جزئیاتی را متوجه می‌شوید که دیگران نادیده می‌گیرند.\n\nگاهی برای تصمیم‌گیری به زمان نیاز دارید، اما شهودتان به ندرت شما را گول می‌زند.",
        "✨ شما شهود پیشرفته‌ای دارید و می‌توانید انرژی اطرافیان را حس کنید.\n\nشما ارتباطات عمیق را ارزش می‌گذارید و در رویدادها به دنبال معنا هستید.\n\nدر دوران تغییر، حساسیت شما به ویژه قوی می‌شود.",
        "🔮 شما ذهن تحلیلگری دارید اما اغلب از غریزه درونی پیروی می‌کنید.\n\nاطرافیان توانایی شما در دیدن ماهیت چیزها را ارزش می‌گذارند.\n\nشما از کسانی هستید که آگاهانه تصمیم می‌گیرند — اما بدون شهود نه.",
        "🌟 شما کسی هستید که تغییرات را پیش از وقوع احساس می‌کند.\n\nاین حساسیت نقطه قوت شماست، نه ضعف.\n\nصدای درونی شما در لحظه مناسب راهنمایتان می‌کند.",
        "🌙 در شما قدرت و ملایمت با هم آمیخته‌اند.\n\nشما می‌توانید عمیق احساس کنید و در عین حال هسته درونی خود را حفظ کنید.\n\nهمین است که افراد جویای حمایت و درک را به سوی شما جذب می‌کند.",
    ],
    "tr": [
        "🌙 Siz güçlü bir iç hassasiyete sahip birisiniz.\n\nDiğerlerinin gözden kaçırdığı ayrıntıları sık sık fark edersiniz.\n\nBazen karar vermek için zamana ihtiyaç duyarsınız, ancak sezginiz sizi nadiren yanıltır.",
        "✨ Gelişmiş bir sezgiye ve etrafınızdaki insanların enerjisini hissedebilme yeteneğine sahipsiniz.\n\nDerin bağlantılara değer verirsiniz ve olaylarda anlam ararsınız.\n\nDeğişim dönemlerinde hassasiyetiniz özellikle güçlenir.",
        "🔮 Analitik bir zihne sahipsiniz, ancak çoğunlukla iç güdünüzü takip edersiniz.\n\nÇevrenizdekileri, şeylerin özünü görme yeteneğinizi takdir eder.\n\nSiz, bilinçli kararlar verenlerden birisiniz — ama sezgi olmadan olmaz.",
        "🌟 Siz değişimi olmadan önce hisseden birisiniz.\n\nBu hassasiyet bir zayıflık değil, güçlü yönünüzdür.\n\nİç sesiniz doğru anda sizi doğru yöne yönlendirir.",
        "🌙 Sizde güç ve yumuşaklık bir arada bulunur.\n\nİç özünüzü korurken derin hissedebilirsiniz.\n\nİşte bu, destek ve anlayış arayan insanları size çeken şeydir.",
    ],
}


async def _get_or_create_personality(session: AsyncSession, user_id: int, lang: str = "ru") -> str:
    """Вернуть описание личности на языке пользователя."""
    _templates = PERSONALITY_TEMPLATES.get(lang) or PERSONALITY_TEMPLATES["en"]

    # Для не-RU языков не кэшируем (кэш хранит RU текст)
    if lang != "ru":
        return _templates[user_id % len(_templates)]

    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return random.choice(_templates)

    prefs = dict(profile.preferences or {})
    if "personality" in prefs:
        return prefs["personality"]

    personality = _templates[user_id % len(_templates)]
    prefs["personality"] = personality
    profile.preferences = prefs
    await session.commit()
    return personality


# ─── Форматирование лимитов ───────────────────────────────────────────────────

_LIMIT_LABELS: dict[str, dict[str, str]] = {
    "ru": {
        "ai_messages": "AI‑сообщений", "personal_questions": "Личных вопросов",
        "weekly_reports": "Недельных раскладов", "compatibility": "Совместимостей",
        "daily_forecasts": "Ежедневных прогнозов", "mini_readings": "Мини‑разборов",
        "date_selections": "Подборов дат", "tarot_cards": "Карт дня",
        "matrix_readings": "Матрица судьбы",
    },
    "en": {
        "ai_messages": "AI messages", "personal_questions": "Personal questions",
        "weekly_reports": "Weekly readings", "compatibility": "Compatibility checks",
        "daily_forecasts": "Daily forecasts", "mini_readings": "Mini readings",
        "date_selections": "Date selections", "tarot_cards": "Cards of the day",
        "matrix_readings": "Destiny matrix",
    },
    "fa": {
        "ai_messages": "پیام‌های هوش مصنوعی", "personal_questions": "سوالات شخصی",
        "weekly_reports": "پیش‌بینی هفتگی", "compatibility": "بررسی سازگاری",
        "daily_forecasts": "پیش‌بینی روزانه", "mini_readings": "بررسی کوتاه",
        "date_selections": "انتخاب تاریخ", "tarot_cards": "کارت روز",
        "matrix_readings": "ماتریس سرنوشت",
    },
    "tr": {
        "ai_messages": "AI mesajları", "personal_questions": "Kişisel sorular",
        "weekly_reports": "Haftalık yorumlar", "compatibility": "Uyumluluk kontrolleri",
        "daily_forecasts": "Günlük tahminler", "mini_readings": "Mini yorumlar",
        "date_selections": "Tarih seçimleri", "tarot_cards": "Günün kartları",
        "matrix_readings": "Kader matrisi",
    },
}

_PLAN_LABELS: dict[str, dict[str, str]] = {
    "ru": {"free": "Бесплатный", "lite": "💫 Lite", "premium": "🌟 Premium", "pro": "🔥 Pro"},
    "en": {"free": "Free",       "lite": "💫 Lite", "premium": "🌟 Premium", "pro": "🔥 Pro"},
    "fa": {"free": "رایگان",     "lite": "💫 Lite", "premium": "🌟 Premium", "pro": "🔥 Pro"},
    "tr": {"free": "Ücretsiz",   "lite": "💫 Lite", "premium": "🌟 Premium", "pro": "🔥 Pro"},
}


async def _build_cabinet_text(session: AsyncSession, user: User, lang: str = "ru"):
    from bot.services.limits import is_vip, get_vip_limits_summary

    _is_vip = await is_vip(user.id)

    if _is_vip:
        # VIP active — show limits
        vip_limits = await get_vip_limits_summary(user.id)
        personality = await _get_or_create_personality(session, user.id, lang)

        pq = vip_limits.get("personal_question", {}).get("remaining", 0)
        mr = vip_limits.get("mini_reading", {}).get("remaining", 0)
        tc = vip_limits.get("tarot_card", {}).get("remaining", 0)
        fm = vip_limits.get("full_matrix", {}).get("remaining", 0)
        cp = vip_limits.get("compatibility", {}).get("remaining", 0)
        wr = vip_limits.get("weekly_report", {}).get("remaining", 0)
        ds = vip_limits.get("date_selection", {}).get("remaining", 0)

        text = (
            "💎 *Тариф VIP — активен*\n\n"
            "📊 *Осталось в этом месяце:*\n"
            f"• 🔮 Личные вопросы: {pq} из 30\n"
            f"• 📖 Мини-разборы: {mr} из 20\n"
            "• 🃏 Карта дня: каждый день\n"
            f"• 🌟 Матрица судьбы: {fm} из 3\n"
            f"• 💞 Совместимость: {cp} из 10\n"
            f"• 📅 Расклад на неделю: {wr} из 4\n"
            f"• 🎯 Подбор дат: {ds} из 5\n\n"
            "━━━━━━━━━━━━━━━\n"
            f"{personality}"
        )
        return text, True  # is_vip=True
    else:
        # Not VIP — show offer
        text = (
            "💎 *Тариф VIP — 1 999 ₽/мес*\n\n"
            "Полный доступ ко всем разделам:\n"
            "• 🔮 Личные вопросы — до 30 в месяц\n"
            "• 📖 Мини-разборы — до 20 в месяц\n"
            "• 🃏 Карта дня — каждый день\n"
            "• 🌟 Матрица судьбы — 3 в месяц\n"
            "• 💞 Совместимость — 10 в месяц\n"
            "• 📅 Расклад на неделю — 4 в месяц\n"
            "• 🎯 Подбор дат — 5 в месяц\n\n"
            "💰 *Экономия:*\n"
            "По отдельности всё это стоит 5 718 ₽\n"
            "С VIP вы платите 1 999 ₽ — экономия 65%\n\n"
            "Без покупки каждого раздела отдельно."
        )
        return text, False  # is_vip=False


def _cabinet_kb(is_vip: bool = False, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    if is_vip:
        rows.append([InlineKeyboardButton(text="🔄 Продлить VIP", callback_data="pay:vip:renew")])
    else:
        rows.append([InlineKeyboardButton(text="💎 Приобрести VIP — 1 999 ₽", callback_data="pay:card:product:vip")])
        rows.append([InlineKeyboardButton(text="⭐ Приобрести VIP — 1 999 Stars", callback_data="pay:stars:product:vip")])
    rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Обработчики ─────────────────────────────────────────────────────────────

@router.message(F.text.in_({"💎 Подписка", "💎 Plans", "💎 اشتراک", "💎 Abonelik"}))
async def reply_cabinet(message: Message, user: User, session: AsyncSession, state: FSMContext, lang: str = "ru"):
    t0 = time.monotonic()
    logger.info("MENU_HANDLER_STARTED handler=reply_cabinet user=%s", message.from_user.id)
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    from bot.utils import show_menu_message
    text, _is_vip = await _build_cabinet_text(session, user, lang)
    await show_menu_message(message, user.telegram_id, text, _cabinet_kb(_is_vip, lang), force_new=True, fast=True)
    logger.info("MENU_RENDER_DONE handler=reply_cabinet duration_ms=%.0f", (time.monotonic() - t0) * 1000)


@router.callback_query(F.data == "cabinet:open")
async def cb_cabinet_open(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    text, _is_vip = await _build_cabinet_text(session, user, lang)
    try:
        await callback.message.edit_text(text, reply_markup=_cabinet_kb(_is_vip, lang), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=_cabinet_kb(_is_vip, lang), parse_mode="Markdown")
    await callback.answer()
