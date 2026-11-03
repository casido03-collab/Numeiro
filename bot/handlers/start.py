import logging
import random
import time
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.keyboards.main import main_menu, plans_keyboard
from bot.models.user import User, Referral
from bot.services.limits import get_user_plan
from bot.handlers.onboarding import start_onboarding
from bot.sponsor_track import track_sponsor_start, track_self

router = Router()
logger = logging.getLogger(__name__)


# ─── Welcome текст для /start ─────────────────────────────────────────────────

def _welcome_text(name: str | None, lang: str = "ru") -> str:
    """Полный приветственный текст над главным меню."""
    from bot.i18n.translations import t
    _hi = {"ru": "Привет", "en": "Hi", "fa": "سلام", "tr": "Merhaba"}.get(lang, "Hi")
    greeting = f"🌟 *{_hi}, {name}!*\n\n" if name else ""
    return greeting + t("welcome", lang)

# ─── Dynamic headers ──────────────────────────────────────────────────────────

_HEADERS_WITH_NAME = [
    "✨ {name}, некоторые ответы уже ждут вас.",
    "🌙 {name}, сегодня интуиция может быть особенно сильной.",
    "🔮 {name}, выберите направление которое сейчас откликается сильнее всего.",
    "✨ {name}, иногда один вопрос меняет взгляд на ситуацию.",
    "🌌 {name}, некоторые совпадения не случайны.",
    "❤️ {name}, возможно именно сейчас вы ищете важный ответ.",
    "🌙 {name}, сегодня особенно важны внутренние ощущения.",
    "✨ {name}, ваше персональное пространство готово.",
    "🔮 {name}, с чего начнём сегодня?",
    "🌙 {name}, выберите то что волнует вас сейчас больше всего.",
]

_HEADERS_UNIVERSAL = [
    "🌌 Некоторые знаки приходят не случайно.",
    "❤️ Иногда человеку нужен всего один ответ.",
    "✨ Ваше персональное пространство готово.",
    "🌙 Сегодня особенно сильна энергия внутренних перемен.",
    "🔮 Иногда один вопрос способен изменить взгляд на ситуацию.",
]


def random_header(name: str | None) -> str:
    """Случайная приветственная строка над инлайн-меню."""
    if name:
        pool = _HEADERS_WITH_NAME + _HEADERS_UNIVERSAL
        h = random.choice(pool)
        return h.format(name=name) if "{name}" in h else h
    return random.choice(_HEADERS_UNIVERSAL)





@router.message(CommandStart())
async def cmd_start(message: Message, user: User, session: AsyncSession, state: FSMContext, lang: str = "ru"):
    t0 = time.monotonic()
    tg_id = message.from_user.id
    # Имя берём из Telegram-объекта — оно никогда не None в отличие от user.first_name
    name = message.from_user.first_name or None
    logger.info("MENU_HANDLER_STARTED handler=cmd_start telegram_id=%s user_db_id=%s name=%s", tg_id, getattr(user, "id", "?"), name)

    # ── 1. Сбросить FSM ──────────────────────────────────────────────────────
    try:
        await state.clear()
        logger.info("CMD_START: FSM CLEARED")
    except Exception:
        logger.exception("CMD_START: state.clear() failed — continuing anyway")

    await track_sponsor_start(message, "numerelogia_astro_bot")
    await track_self(message, "numerelogia_astro_bot")

    # ── 2. Deeplink / реферальный код ────────────────────────────────────────
    try:
        args = (message.text or "").split()
        if len(args) > 1:
            arg = args[1]
            logger.info("CMD_START: start arg=%s", arg)

            # Подтверждение перехода через bubbles-партнёрскую ссылку
            if arg.startswith("bub_"):
                import aiohttp
                try:
                    async with aiohttp.ClientSession() as _s:
                        await _s.post(
                            "https://drawme.live/api/astro_verify",
                            json={"user_id": str(message.from_user.id), "secret": "bubbles_astro_2024"},
                            timeout=aiohttp.ClientTimeout(total=5),
                        )
                except Exception:
                    pass

            # Оплата подписки бизнес-чата через Stars
            if arg == "biz990":
                from aiogram.types import LabeledPrice
                await message.answer(
                    "✨ *Подписка — работа с Бабушкой Aisha*\n\n"
                    "Задавайте вопросы каждый день — я буду отвечать лично, глубоко и честно.\n\n"
                    "💎 *990 Stars / месяц* — 3 вопроса в день",
                    parse_mode="Markdown",
                )
                await message.answer_invoice(
                    title="Работа с Бабушкой Aisha — месяц",
                    description="3 AI-вопроса в день в личном чате с Бабушкой Aisha",
                    payload="biz_monthly_990",
                    currency="XTR",
                    prices=[LabeledPrice(label="Подписка на месяц", amount=990)],
                )
                return

            await _process_referral(message, user, arg, session)
            logger.info("CMD_START: referral processed")
    except Exception:
        logger.exception("CMD_START: start arg processing failed — continuing anyway")

    # ── 3. Всегда показываем выбор языка (сброс языка при /start) ────────────
    logger.info("CMD_START: showing lang selection, name=%s", name)
    try:
        from bot.handlers.lang_select import send_lang_selection
        await send_lang_selection(message)
        logger.info("CMD_START: lang selection sent")
        logger.info("MENU_RENDER_DONE handler=cmd_start duration_ms=%.0f", (time.monotonic() - t0) * 1000)
    except Exception:
        logger.exception("CMD_START: lang selection failed — showing fallback menu")
        await _send_fallback_menu(message, name)


async def _send_fallback_menu(message: Message, name: str | None) -> None:
    """Аварийный ответ — всегда показать хоть что-то."""
    greeting = f"🌟 *Привет, {name}!*\n\n" if name else ""
    try:
        await message.answer(
            f"{greeting}✨ Добро пожаловать в Aisha AI!\n\n_Выбери, с чего начать:_",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("CMD_START: fallback message also failed: %s", e)


async def _process_referral(
    message: Message, user: User, ref_code: str, session: AsyncSession
):
    """Обработать реферальный код из /start ref_XXXXXXX."""
    if not ref_code.startswith("ref_"):
        return

    try:
        inviter_tg_id = int(ref_code[4:])
    except ValueError:
        return

    # Self-referral protection
    if inviter_tg_id == user.telegram_id:
        return

    # Уже есть пригласивший
    if user.invited_by:
        return

    # Найти пригласителя
    inviter_res = await session.execute(
        select(User).where(User.telegram_id == inviter_tg_id)
    )
    inviter = inviter_res.scalar_one_or_none()
    if not inviter:
        return

    # Защита от дублей
    existing = await session.execute(
        select(Referral).where(Referral.invited_telegram_id == user.telegram_id)
    )
    if existing.scalar_one_or_none():
        return

    # Сохранить связь
    user.invited_by = inviter_tg_id
    session.add(Referral(
        inviter_telegram_id=inviter_tg_id,
        invited_telegram_id=user.telegram_id,
    ))
    await session.commit()


@router.callback_query(F.data == "menu:main")
async def menu_main(callback: CallbackQuery, user: User, lang: str = "ru"):
    from bot.handlers.sponsor import get_sponsor_state, show_sponsor_screen, is_subscribed
    sponsor = await get_sponsor_state()
    if sponsor["enabled"] and sponsor["channel"]:
        subscribed = await is_subscribed(callback.message.bot, callback.from_user.id, sponsor["channel"])
        if not subscribed:
            await show_sponsor_screen(callback, callback.message.bot, sponsor["link"])
            return

    from bot.utils import replace_message, ensure_keyboard
    name = user.first_name or None
    await replace_message(callback.message, random_header(name), reply_markup=main_menu(lang))
    await ensure_keyboard(callback.message, user.telegram_id)
    await callback.answer()


@router.callback_query(F.data == "menu:plans")
async def menu_plans(callback: CallbackQuery, lang: str = "ru"):
    _text = {
        "ru": (
            "✨ <b>Разделы и цены</b>\n\n"
            "🔯 Гороскоп дня — <b>бесплатно</b>\n"
            "⚡ Энергия дня — <b>бесплатно</b>\n"
            "🃏 Карта дня — <b>49 ₽ / 49 ⭐</b>\n"
            "🔮 Личный вопрос — <b>29 ₽ / 29 ⭐</b>\n"
            "📖 Мини-разбор — <b>49 ₽ / 49 ⭐</b>\n"
            "🌟 Матрица судьбы — <b>199 ₽ / 199 ⭐</b>\n"
            "💞 Совместимость — <b>99 ₽ / 99 ⭐</b>\n"
            "📅 Расклад на неделю — <b>79 ₽ / 79 ⭐</b>\n"
            "🎯 Подбор дат — <b>99 ₽ / 99 ⭐</b>"
        ),
        "en": (
            "✨ <b>Features & prices</b>\n\n"
            "🔯 Daily horoscope — <b>free</b>\n"
            "⚡ Daily energy — <b>free</b>\n"
            "🃏 Card of the day — <b>49 ⭐</b>\n"
            "🔮 Personal question — <b>29 ⭐</b>\n"
            "📖 Mini reading — <b>49 ⭐</b>\n"
            "🌟 Destiny matrix — <b>199 ⭐</b>\n"
            "💞 Compatibility — <b>99 ⭐</b>\n"
            "📅 Weekly reading — <b>79 ⭐</b>\n"
            "🎯 Date selection — <b>99 ⭐</b>"
        ),
        "fa": (
            "✨ <b>بخش‌ها و قیمت‌ها</b>\n\n"
            "🔯 طالع‌بینی روزانه — <b>رایگان</b>\n"
            "⚡ انرژی روز — <b>رایگان</b>\n"
            "🃏 کارت روز — <b>49 ⭐</b>\n"
            "🔮 سؤال شخصی — <b>29 ⭐</b>\n"
            "📖 تحلیل کوتاه — <b>49 ⭐</b>\n"
            "🌟 ماتریس سرنوشت — <b>199 ⭐</b>\n"
            "💞 سازگاری — <b>99 ⭐</b>\n"
            "📅 فال هفتگی — <b>79 ⭐</b>\n"
            "🎯 انتخاب تاریخ — <b>99 ⭐</b>"
        ),
        "tr": (
            "✨ <b>Bölümler ve fiyatlar</b>\n\n"
            "🔯 Günlük burç — <b>ücretsiz</b>\n"
            "⚡ Günlük enerji — <b>ücretsiz</b>\n"
            "🃏 Günün kartı — <b>49 ⭐</b>\n"
            "🔮 Kişisel soru — <b>29 ⭐</b>\n"
            "📖 Mini yorum — <b>49 ⭐</b>\n"
            "🌟 Kader matrisi — <b>199 ⭐</b>\n"
            "💞 Uyumluluk — <b>99 ⭐</b>\n"
            "📅 Haftalık açılım — <b>79 ⭐</b>\n"
            "🎯 Tarih seçimi — <b>99 ⭐</b>"
        ),
    }.get(lang, "")
    await callback.message.edit_text(_text, reply_markup=plans_keyboard(lang), parse_mode="HTML")
    await callback.answer()
