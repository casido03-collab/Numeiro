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
    plan = await get_user_plan(session, user.id)
    limit_labels = _LIMIT_LABELS.get(lang) or _LIMIT_LABELS["en"]
    plan_labels = _PLAN_LABELS.get(lang) or _PLAN_LABELS["en"]
    plan_label = plan_labels.get(plan, plan)

    # Дата окончания
    sub_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = sub_result.scalar_one_or_none()
    expires_str = "—"
    _expired = {"ru": "Истекла", "en": "Expired", "fa": "منقضی شده", "tr": "Süresi doldu"}.get(lang, "Expired")
    if sub and sub.expires_at:
        if sub.status == SubscriptionStatusEnum.active:
            expires_str = sub.expires_at.strftime("%d.%m.%Y")
        else:
            expires_str = _expired

    # Лимиты
    limits = await get_limits_summary(session, user.id)
    personality = await _get_or_create_personality(session, user.id, lang)

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend

    _of = {"ru": "из", "en": "of", "fa": "از", "tr": "/"}.get(lang, "of")
    lines_limits = []
    for key, label in limit_labels.items():
        info = limits.get(key, {})
        remaining = info.get("remaining", 0)
        max_val = info.get("max", 0)
        if max_val > 0:
            lines_limits.append(f"• {label}: *{remaining}* {_of} {max_val}")

    _no_limits = {
        "ru": "• Лимиты недоступны на бесплатном тарифе",
        "en": "• Limits are not available on the free plan",
        "fa": "• محدودیت‌ها در طرح رایگان موجود نیست",
        "tr": "• Ücretsiz planda limitler mevcut değil",
    }.get(lang, "• Limits are not available on the free plan")
    limits_block = "\n".join(lines_limits) if lines_limits else _no_limits

    _lbl_free = {"ru": "📊 *Остаток (всего):*", "en": "📊 *Balance (total):*", "fa": "📊 *موجودی (کل):*", "tr": "📊 *Bakiye (toplam):*"}.get(lang, "📊 *Balance (total):*")
    _lbl_paid = {"ru": "📊 *Остаток за период:*", "en": "📊 *Balance for period:*", "fa": "📊 *موجودی دوره:*", "tr": "📊 *Dönem bakiyesi:*"}.get(lang, "📊 *Balance for period:*")
    limits_label = _lbl_free if plan == "free" else _lbl_paid

    _title  = {"ru": "Персональное пространство", "en": "Personal Space", "fa": "فضای شخصی", "tr": "Kişisel Alan"}.get(lang, "Personal Space")
    _plan_l = {"ru": "Тариф", "en": "Plan", "fa": "طرح", "tr": "Plan"}.get(lang, "Plan")
    _until  = {"ru": "Активен до", "en": "Active until", "fa": "فعال تا", "tr": "Aktif"}.get(lang, "Active until")

    matrix_remaining = limits.get("matrix_readings", {}).get("remaining", 0)
    show_matrix = matrix_remaining > 0

    text = (
        f"✨ *{_title} — {name}*\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 *{_plan_l}:* {plan_label}\n"
        f"📅 *{_until}:* {expires_str}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{limits_label}\n"
        f"{limits_block}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{personality}"
    )
    return text, show_matrix


def _cabinet_kb(show_matrix: bool = False, lang: str = "ru") -> InlineKeyboardMarkup:
    _matrix  = {"ru": "🌟 Матрица судьбы",          "en": "🌟 Destiny Matrix",         "fa": "🌟 ماتریس سرنوشت",     "tr": "🌟 Kader Matrisi"}.get(lang, "🌟 Destiny Matrix")
    _renew   = {"ru": "💎 Продлить / сменить тариф", "en": "💎 Renew / change plan",    "fa": "💎 تمدید / تغییر طرح", "tr": "💎 Yenile / plan değiştir"}.get(lang, "💎 Renew / change plan")
    _all     = {"ru": "📋 Все тарифы",               "en": "📋 All plans",              "fa": "📋 همه طرح‌ها",        "tr": "📋 Tüm planlar"}.get(lang, "📋 All plans")
    _menu    = {"ru": "🔮 Главное меню",              "en": "🔮 Main menu",              "fa": "🔮 منوی اصلی",         "tr": "🔮 Ana menü"}.get(lang, "🔮 Main menu")
    rows = []
    if show_matrix:
        rows.append([InlineKeyboardButton(text=_matrix, callback_data="matrix:start")])
    rows += [
        [InlineKeyboardButton(text=_renew, callback_data="menu:main")],
        [InlineKeyboardButton(text=_all,   callback_data="menu:main")],
        [InlineKeyboardButton(text=_menu,  callback_data="menu:main")],
    ]
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
    text, show_matrix = await _build_cabinet_text(session, user, lang)
    await show_menu_message(message, user.telegram_id, text, _cabinet_kb(show_matrix, lang), force_new=True, fast=True)
    logger.info("MENU_RENDER_DONE handler=reply_cabinet duration_ms=%.0f", (time.monotonic() - t0) * 1000)


@router.callback_query(F.data == "cabinet:open")
async def cb_cabinet_open(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    text, show_matrix = await _build_cabinet_text(session, user, lang)
    try:
        await callback.message.edit_text(text, reply_markup=_cabinet_kb(show_matrix, lang), parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=_cabinet_kb(show_matrix, lang), parse_mode="Markdown")
    await callback.answer()
