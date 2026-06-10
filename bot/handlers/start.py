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
from bot.handlers.onboarding import is_onboarding_done, start_onboarding

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


PLANS_TEXT = """📜 <b>Тарифы Aisha AI</b>

Ваш текущий тариф: <b>{current_plan}</b>

━━━━━━━━━━━━━━━
🆓 <b>Бесплатно</b> (лимиты даются один раз)
• 10 AI‑сообщений
• 1 вопрос Бабушке Aisha
• 1 Гороскоп на день
• 1 Энергия дня (ежедневно)
• 1 мини‑разбор
• 1 совместимость
• 1 Карта дня

━━━━━━━━━━━━━━━
💫 <b>Lite</b> — 299 ₽ / 7 дней
• 120 AI‑сообщений
• 7 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 1 совместимость
• 2 подбора благоприятных дат
• 3 Энергии дня
• 3 мини‑разбора
• 5 Карт дня
• Недельный расклад — разовая покупка

━━━━━━━━━━━━━━━
🌟 <b>Premium</b> — 999 ₽ / месяц
• 800 AI‑сообщений
• 30 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 2 недельных расклада
• 7 совместимостей
• 30 Энергий дня
• 15 мини‑разборов
• 10 подборов благоприятных дат
• 10 Карт дня

━━━━━━━━━━━━━━━
🔥 <b>Pro</b> — 1 499 ₽ / месяц
• 3 000 AI‑сообщений
• 60 вопросов Бабушке Aisha
• 1 Гороскоп на день
• 4 недельных расклада
• 30 совместимостей
• 30 Энергий дня
• 50 мини‑разборов
• 40 подборов благоприятных дат
• 30 Карт дня
• 🌟 1 Матрица судьбы в месяц

━━━━━━━━━━━━━━━
*Каждый ответ основан на практиках, наблюдениях и трактовках бабушки Aisha. AI не придумывает ответы, а интерпретирует её знания под вашу ситуацию.

🌟 <b>Матрица судьбы</b> — включена в Pro или разовая покупка 299 ₽ для Lite/Premium.

💎 Разовые покупки доступны по кнопке ниже."""


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

    # ── 2. Deeplink / реферальный код ────────────────────────────────────────
    try:
        args = (message.text or "").split()
        if len(args) > 1:
            arg = args[1]
            logger.info("CMD_START: start arg=%s", arg)

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

    # ── 3. Онбординг или главное меню ────────────────────────────────────────
    try:
        onboarding_done = await is_onboarding_done(session, user.id)
        logger.info("CMD_START: onboarding_done=%s", onboarding_done)
    except Exception:
        logger.exception("CMD_START: is_onboarding_done failed — treating as done")
        onboarding_done = True   # безопаснее показать меню, чем зависнуть

    if not onboarding_done:
        logger.info("CMD_START: ONBOARDING STEP START")
        try:
            # Проверяем — выбран ли язык явно
            from bot.models.user import UserProfile
            from bot.handlers.lang_select import send_lang_selection
            pr = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            ob_profile = pr.scalar_one_or_none()
            explicit_lang = None
            if ob_profile and ob_profile.preferences:
                explicit_lang = ob_profile.preferences.get("lang")

            if explicit_lang:
                await start_onboarding(message, user, explicit_lang)
            else:
                await send_lang_selection(message)
            logger.info("CMD_START: ONBOARDING MESSAGE SENT (lang=%s)", explicit_lang or "selecting")
        except Exception:
            logger.exception("CMD_START: start_onboarding failed — showing fallback menu")
            await _send_fallback_menu(message, name)
        return

    # ── 4. Главное меню для вернувшегося пользователя ────────────────────────
    logger.info("CMD_START: showing main menu, name=%s", name)
    try:
        from bot.utils import show_menu_message, safe_answer_menu
        from bot.keyboards.reply import main_reply_keyboard
        from bot.services.menu_tracker import is_keyboard_shown, mark_keyboard_shown

        # На /start всегда показываем reply-клавиатуру (на случай если пропала)
        sent = await safe_answer_menu(message, "🌙", reply_markup=main_reply_keyboard(), parse_mode=None)
        if sent:
            await mark_keyboard_shown(tg_id)
        logger.info("CMD_START: keyboard sent")

        await show_menu_message(
            message, tg_id,
            _welcome_text(name, lang),
            main_menu(lang),
            force_new=True,
            fast=True,
        )
        logger.info("MENU_RENDER_DONE handler=cmd_start duration_ms=%.0f", (time.monotonic() - t0) * 1000)
    except Exception:
        logger.exception("CMD_START: menu sending failed — showing fallback")
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
async def menu_plans(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    from bot.i18n.translations import t
    plan = await get_user_plan(session, user.id)
    plan_names = {
        "free":    t("plan_free_name", lang),
        "lite":    "Lite",
        "premium": "Premium",
        "pro":     "Pro",
    }
    current = plan_names.get(plan, t("plan_free_name", lang))
    text = PLANS_TEXT.format(current_plan=current)
    await callback.message.edit_text(text, reply_markup=plans_keyboard(lang), parse_mode="HTML")
    await callback.answer()
