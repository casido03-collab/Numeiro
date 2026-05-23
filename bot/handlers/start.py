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

def _welcome_text(name: str | None) -> str:
    """Полный приветственный текст над главным меню (только для /start)."""
    greeting = f"🌟 *Привет, {name}!*\n\n" if name else ""
    return (
        f"{greeting}"
        f"✨ Добро пожаловать в *Aisha AI* — Компаньон собранный по многолетним наработкам Бабушки Аиши\n\n"
        f"Здесь вас ждёт:\n\n"
        f"⚡️ *Энергия дня* — ежедневный бесплатный прогноз\n"
        f"✨ *Мой разбор* — нумерологический анализ по дате рождения _(Лимитированный бесплатный доступ)_\n"
        f"🌟 *Матрица судьбы* — глубокий разбор арканов и энергий\n"
        f"📅 *Прогноз на неделю* — по любой сфере жизни\n"
        f"💞 *Совместимость* — числа двух людей\n"
        f"🔮 *Вопрос Тарологу* — личный вопрос Бабушке Aisha\n\n"
        f"Всё основано на нумерологии, матрице судьбы, а AI интеллект помогает интерпретировать мысли Бабушки Аиши в понятный язык для каждого.\n\n"
        f"_Выберите, с чего начать:_"
    )

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
💫 <b>Lite</b> — 299 ₽ / 7 дней
• 120 AI‑сообщений
• 2 личных вопроса Тарологу*
• 1 совместимость
• 3 Энергии дня
• 3 мини‑разбора

━━━━━━━━━━━━━━━
🌟 <b>Premium</b> — 999 ₽ / месяц
• 800 AI‑сообщений
• 15 личных вопросов Тарологу*
• 2 недельных расклада
• 4 совместимости
• 30 Энергий дня
• 15 мини‑разборов
• 10 подборов благоприятных дат

━━━━━━━━━━━━━━━
🔥 <b>Pro</b> — 1 499 ₽ / месяц
• 3 000 AI‑сообщений
• 60 личных вопросов Тарологу*
• 4 недельных расклада
• 15 совместимостей
• 30 Энергий дня
• 50 мини‑разборов
• 40 подборов благоприятных дат

━━━━━━━━━━━━━━━
*Каждый ответ основан на практиках, наблюдениях и трактовках бабушки Aisha. AI не придумывает ответы, а интерпретирует её знания под вашу ситуацию.

💎 Разовые покупки доступны по кнопке ниже."""


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, session: AsyncSession, state: FSMContext):
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

    # ── 2. Реферальный код (не должен ломать /start при любой ошибке) ────────
    try:
        args = (message.text or "").split()
        if len(args) > 1:
            logger.info("CMD_START: referral arg=%s", args[1])
            await _process_referral(message, user, args[1], session)
            logger.info("CMD_START: referral processed")
    except Exception:
        logger.exception("CMD_START: referral processing failed — continuing anyway")

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
            await start_onboarding(message, user)
            logger.info("CMD_START: ONBOARDING MESSAGE SENT")
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
            _welcome_text(name),
            main_menu(),
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
async def menu_main(callback: CallbackQuery, user: User):
    name = user.first_name or None
    await callback.message.edit_text(
        random_header(name),
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "menu:plans")
async def menu_plans(callback: CallbackQuery, user: User, session: AsyncSession):
    plan = await get_user_plan(session, user.id)
    plan_names = {
        "free": "Бесплатный",
        "lite": "Lite",
        "premium": "Premium",
        "pro": "Pro",
    }
    current = plan_names.get(plan, "Бесплатный")
    text = PLANS_TEXT.format(current_plan=current)
    await callback.message.edit_text(text, reply_markup=plans_keyboard(), parse_mode="HTML")
    await callback.answer()
