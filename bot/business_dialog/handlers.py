"""Handlers для Telegram Business диалога с бабушкой Аишей."""
import json
import logging
import random
from aiogram import Router, Bot
from aiogram.types import Message

from bot.business_dialog.session_manager import (
    get_biz_stage, set_biz_stage,
    store_profile_field, get_profile,
    increment_free_count, get_free_count,
    store_biz_conn, get_biz_conn,
    get_followup_left, decrement_followup,
    set_followup_left, reset_session,
    set_payment_offered,
    append_history, get_history, format_history,
)

_RESET_PHRASE = "сброс12"

_ESOTERIC_EMOJIS = ["🌙", "✨", "💫", "🔮", "🌟", "⭐", "🌌", "💎"]


def _emo() -> str:
    """Случайный эзотерический эмодзи."""
    return random.choice(_ESOTERIC_EMOJIS)

_PAYMENT_READY = [
    "я готова", "я готов", "давайте", "давай попробуем", "попробуем",
    "хочу попробовать", "хочу заказать", "хочу оплатить", "как оплатить",
    "где оплатить", "согласна", "согласен", "берём", "возьмём", "оплачу",
    "закажу", "оформить", "хочу узнать больше", "интересно попробовать",
    "готова платить", "готов платить", "давайте закажу", "давайте попробуем",
    "да, давайте", "да давайте", "ок давайте", "окей давайте",
]


def _wants_to_pay(text: str) -> bool:
    """Определить хочет ли пользователь перейти к оплате."""
    t = text.lower().strip()
    return any(phrase in t for phrase in _PAYMENT_READY)
from bot.business_dialog.typing_simulation import (
    typing_short, typing_medium, typing_long, typing_deflect, typing_for_text
)
from bot.business_dialog.anti_free_chat import get_deflect_message, FREE_MSG_LIMIT
from bot.business_dialog.ai_router import detect_intent, get_product_name
from bot.business_dialog.services import generate_business
from bot.business_dialog.prompts import AISHA_FREE_PROMPT, AISHA_FOLLOWUP_PROMPT, AISHA_PITCH_PROMPT
from bot.business_dialog.tribute_flow import payment_keyboard, return_payment_keyboard, TRIBUTE_PRICE

router = Router(name="business_handlers")
logger = logging.getLogger(__name__)

# Получить session_maker из router.py после инициализации
_session_maker = None


def _set_session_maker(sm):
    global _session_maker
    _session_maker = sm


# ─── Вспомогательная отправка через business_connection ───────────────────────

async def _send(
    bot: Bot,
    chat_id: int,
    text: str,
    biz_conn_id: str | None,
    reply_markup=None,
) -> None:
    kwargs: dict = {"chat_id": chat_id, "text": text, "parse_mode": None}
    if biz_conn_id:
        kwargs["business_connection_id"] = biz_conn_id
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    try:
        await bot.send_message(**kwargs)
    except Exception as e:
        logger.warning("business _send failed (tid=%s): %s", chat_id, e)


# ─── Главный роутер входящих business-сообщений ───────────────────────────────

@router.business_message()
async def handle_business_message(message: Message, bot: Bot) -> None:
    if not message.from_user:
        return

    telegram_id = message.from_user.id
    chat_id     = message.chat.id
    text        = (message.text or "").strip()
    biz_conn_id = message.business_connection_id

    # Всегда сохраняем актуальный business_connection_id
    if biz_conn_id:
        await store_biz_conn(telegram_id, biz_conn_id)

    # Кодовая фраза сброса сессии (для тестирования)
    if text.lower() == _RESET_PHRASE:
        await reset_session(telegram_id)
        await _reset_db_session(telegram_id)
        await _send(bot, chat_id, "🔄 Сессия сброшена. Пишите — начнём заново.", biz_conn_id)
        return

    stage = await get_biz_stage(telegram_id)
    logger.info("business_msg tid=%s stage=%s text=%.40s", telegram_id, stage, text)

    if stage in ("new", ""):
        await _stage_new(bot, chat_id, telegram_id, biz_conn_id, message)
    elif stage == "collecting_name":
        await _stage_name(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "collecting_birth_date":
        await _stage_birth_date(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "collecting_city":
        await _stage_city(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "collecting_problem":
        await _stage_problem(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "free_dialog":
        await _stage_free_dialog(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "waiting_payment":
        await _stage_waiting_payment(bot, chat_id, telegram_id, biz_conn_id)
    elif stage in ("paid",):
        await _send(bot, chat_id, f"Душа моя {_emo()} Я уже смотрю вашу ситуацию. Совсем скоро…", biz_conn_id)
    elif stage == "followup":
        await _stage_followup(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "completed":
        await _stage_completed(bot, chat_id, telegram_id, biz_conn_id)


# ─── Двухшаговое предложение оплаты ──────────────────────────────────────────

_BRIDGE_TEXTS = [
    "Но такие вещи я смотрю глубже и спокойно, чтобы ничего не упустить.\n\nЕсли хотите — я готова начать полный просмотр.",
    "Это требует тихого и внимательного взгляда — не торопясь, по всем линиям.\n\nЯ готова, если вы разрешите.",
    "Такие ситуации лучше смотреть целиком — иначе можно упустить самое важное.\n\nСкажите слово — и я приступлю.",
    "Здесь есть то, что нужно рассмотреть спокойно и полностью.\n\nЕсли хотите — я могу сделать это прямо сейчас.",
]

_PAYMENT_TEXTS = [
    "Разбор почти готов — осталось только ваше разрешение начать {e}\n\n✨ «{p}» — {price} ₽\n\nПосле оплаты приступлю сразу же.",
    "Всё что нужно — уже у меня {e}\n\n✨ «{p}» — {price} ₽\n\nОплатите — и я немедленно начну смотреть.",
    "Я уже подготовила для вас разбор, он ждёт {e}\n\n✨ «{p}» — {price} ₽\n\nКак только оплата пройдёт — сразу приступлю.",
]


async def _send_payment_offer(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    profile: dict,
) -> None:
    """Три сообщения с паузами: тизер → мягкий переход → счёт с кнопкой."""
    prod_name = profile.get("product_name", "Разбор ситуации")
    context   = json.dumps({
        "name":       profile.get("name", ""),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
        "intent":     profile.get("intent", ""),
        "product":    prod_name,
    }, ensure_ascii=False)

    # Блокируем стадию сразу — если клиент напишет во время пауз,
    # попадёт в _stage_waiting_payment (мягкий deflect), а не сюда снова
    await set_biz_stage(telegram_id, "waiting_payment")
    await set_payment_offered(telegram_id)

    # Сообщение 1 — короткий AI-тизер (2 предложения + многоточие)
    teaser = await generate_business(
        AISHA_PITCH_PROMPT,
        f"Данные клиента: {context}",
        complexity="simple",
        max_tokens=90,
    )
    await typing_for_text(bot, chat_id, biz_conn_id, teaser)
    await _send(bot, chat_id, teaser, biz_conn_id)

    # Сообщение 2 — мягкий переход (рандом, пауза 5–8 сек)
    bridge = random.choice(_BRIDGE_TEXTS)
    await typing_long(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, bridge, biz_conn_id)

    # Сообщение 3 — счёт с кнопкой
    payment_text = random.choice(_PAYMENT_TEXTS).format(
        e=_emo(), p=prod_name, price=TRIBUTE_PRICE
    )
    await typing_medium(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, payment_text, biz_conn_id, reply_markup=payment_keyboard())

    # (стадия и payment_offered уже выставлены в начале функции)


# ─── Этапы диалога ────────────────────────────────────────────────────────────

async def _stage_new(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, message: Message) -> None:
    """Первое сообщение — приветствие и запрос имени."""
    await set_biz_stage(telegram_id, "collecting_name")

    # Сохраним имя из Telegram как подсказку
    tg_name = message.from_user.first_name or "" if message.from_user else ""
    if tg_name:
        await store_profile_field(telegram_id, "tg_name", tg_name)

    # Создаём запись в БД (нужна для системы напоминаний)
    await _ensure_db_session(telegram_id, biz_conn_id)

    welcome = f"Здравствуйте, душа моя {_emo()}\n\nРада, что вы написали. Скажите — как вас зовут?"
    await typing_for_text(bot, chat_id, biz_conn_id, welcome)
    await _send(bot, chat_id, welcome, biz_conn_id)


async def _stage_name(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    if not text:
        await _send(bot, chat_id, f"Напишите своё имя {_emo()}", biz_conn_id)
        return

    name = text.strip().split()[0].capitalize()
    await store_profile_field(telegram_id, "name", name)
    await set_biz_stage(telegram_id, "collecting_birth_date")

    response = (
        f"Как хорошо, {name} {_emo()} Чтобы я смогла посмотреть вашу ситуацию глубже — "
        f"скажите, когда вы родились?\nНапишите дату вот так: 15.03.1990"
    )
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)


async def _stage_birth_date(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    if not text:
        await _send(bot, chat_id, f"Напишите дату рождения в формате дд.мм.гггг {_emo()}", biz_conn_id)
        return

    await store_profile_field(telegram_id, "birth_date", text)
    await set_biz_stage(telegram_id, "collecting_city")

    response = f"Благодарю вас {_emo()} И последний вопрос прежде чем мы начнём — в каком городе вы живёте?"
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)


def _problem_intros(name: str) -> list[str]:
    e = _emo()
    return [
        f"Моя хорошая {name} {e}\n\nРасскажите спокойно — что сейчас тревожит больше всего? Напишите своими словами, я слушаю.",
        f"{name}, я здесь рядом {e}\n\nЧто сейчас лежит на сердце? Расскажите — не торопитесь.",
        f"Слышу вас, {name} {e}\n\nЧто сейчас тревожит? Напишите своими словами.",
        f"{name}, расскажите — что сейчас беспокоит больше всего? {e} Я здесь и слушаю.",
    ]


async def _stage_city(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    if not text:
        await _send(bot, chat_id, f"Напишите название города {_emo()}", biz_conn_id)
        return

    await store_profile_field(telegram_id, "city", text)
    await set_biz_stage(telegram_id, "collecting_problem")

    profile = await get_profile(telegram_id)
    name = profile.get("name", "вы")

    intro = random.choice(_problem_intros(name))
    await typing_for_text(bot, chat_id, biz_conn_id, intro)
    await _send(bot, chat_id, intro, biz_conn_id)


async def _stage_problem(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    if not text or len(text) < 5:
        await _send(bot, chat_id, f"Расскажите подробнее, душа моя {_emo()}", biz_conn_id)
        return

    await store_profile_field(telegram_id, "problem", text)

    intent       = detect_intent(text)
    product_name = get_product_name(intent)
    await store_profile_field(telegram_id, "intent", intent)
    await store_profile_field(telegram_id, "product_name", product_name)
    await set_biz_stage(telegram_id, "free_dialog")

    profile = await get_profile(telegram_id)

    # Первый AI-ответ — тепло, коротко, показываем что начали смотреть
    context = json.dumps({
        "name":       profile.get("name", ""),
        "birth_date": profile.get("birth_date", ""),
        "city":       profile.get("city", ""),
        "problem":    text,
        "product":    product_name,
        "stage":      "initial_response",
    }, ensure_ascii=False)

    await append_history(telegram_id, "user", text)
    response = await generate_business(
        AISHA_FREE_PROMPT,
        f"Человек описал свою ситуацию. Ответь тепло и очень коротко — покажи что начала смотреть. "
        f"Задай один уточняющий вопрос, которого ещё не задавала. Обращайся на вы. Данные: {context}",
        complexity="simple",
        max_tokens=150,
    )
    await append_history(telegram_id, "aisha", response)
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)
    await increment_free_count(telegram_id)


async def _stage_free_dialog(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    # Если пользователь сам выражает готовность оплатить — плавно переходим к оплате
    if _wants_to_pay(text):
        profile = await get_profile(telegram_id)
        await _send_payment_offer(bot, chat_id, telegram_id, biz_conn_id, profile)
        return

    free_count = await get_free_count(telegram_id)

    # После лимита — переключаемся на deflect + предложение оплаты
    if free_count >= FREE_MSG_LIMIT:
        await typing_deflect(bot, chat_id, biz_conn_id)
        deflect = await get_deflect_message(telegram_id)
        await _send(bot, chat_id, deflect, biz_conn_id)

        profile = await get_profile(telegram_id)
        await _send_payment_offer(bot, chat_id, telegram_id, biz_conn_id, profile)
        return

    # Ещё в зоне бесплатного — короткий AI-ответ с историей
    profile = await get_profile(telegram_id)
    history = await get_history(telegram_id)
    history_text = format_history(history)

    await append_history(telegram_id, "user", text)

    context = json.dumps({
        "name":       profile.get("name", ""),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
    }, ensure_ascii=False)

    response = await generate_business(
        AISHA_FREE_PROMPT,
        f"ИСТОРИЯ ПЕРЕПИСКИ:\n{history_text}\n\n"
        f"ПОСЛЕДНЕЕ СООБЩЕНИЕ КЛИЕНТА: {text}\n\n"
        f"Данные клиента: {context}\n\n"
        f"Ответь коротко (2–3 предложения). Не повторяй вопросы из истории. "
        f"Если клиент говорит 'я уже сказал' или 'я писал' — признай это и двигайся вперёд. "
        f"Обращайся на вы.",
        complexity="simple",
        max_tokens=140,
    )
    await append_history(telegram_id, "aisha", response)
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)
    await increment_free_count(telegram_id)


async def _stage_waiting_payment(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None) -> None:
    """Пользователь пишет, но ещё не оплатил — мягкий deflect + кнопка возврата."""
    await typing_deflect(bot, chat_id, biz_conn_id)
    deflect = await get_deflect_message(telegram_id)
    await _send(bot, chat_id, deflect, biz_conn_id)

    await typing_short(bot, chat_id, biz_conn_id)
    await _send(
        bot, chat_id,
        f"Душа моя, я оставила ваш разбор открытым {_emo()} Когда будете готовы — просто нажмите кнопку.",
        biz_conn_id,
        reply_markup=return_payment_keyboard(),
    )


async def _stage_followup(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    """Уточняющие вопросы после платной консультации (max 2)."""
    left = await decrement_followup(telegram_id)

    profile = await get_profile(telegram_id)

    context = json.dumps({
        "name":           profile.get("name", ""),
        "birth_date":     profile.get("birth_date", ""),
        "problem":        profile.get("problem", ""),
        "followups_left": left,
    }, ensure_ascii=False)

    response = await generate_business(
        AISHA_FOLLOWUP_PROMPT,
        f"Уточняющий вопрос после консультации: {text}\n\nДанные: {context}\n\nОбращайся на вы.",
        complexity="medium",
        max_tokens=300,
    )
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)

    if left == 0:
        await set_biz_stage(telegram_id, "completed")
        await typing_short(bot, chat_id, biz_conn_id)
        closing = random.choice([
            f"Если почувствуете, что ситуация снова тревожит — можете написать мне {_emo()}",
            f"Если захотите посмотреть глубже — возвращайтесь. Иногда спустя время открываются новые линии {_emo()}",
            f"Берегите себя, душа моя {_emo()} Если понадоблюсь — я здесь.",
        ])
        await _send(bot, chat_id, closing, biz_conn_id)


async def _stage_completed(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None) -> None:
    """Консультация завершена — тёплые завершающие фразы."""
    msgs = [
        f"Если почувствуете, что ситуация снова тревожит — можете написать мне {_emo()}",
        f"Иногда спустя время открываются новые линии ситуации {_emo()}",
        f"Если захотите посмотреть глубже — возвращайтесь, душа моя {_emo()}",
        f"Я здесь {_emo()}",
    ]
    await typing_short(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, random.choice(msgs), biz_conn_id)


# ─── Создание/обновление DB-записи сессии ─────────────────────────────────────

async def _reset_db_session(telegram_id: int) -> None:
    """Удалить BusinessSession из БД (для полного сброса при тестировании)."""
    if not _session_maker:
        return
    try:
        from sqlalchemy import delete
        from bot.business_dialog.models import BusinessSession, BusinessProfile
        async with _session_maker() as session:
            await session.execute(delete(BusinessSession).where(BusinessSession.telegram_id == telegram_id))
            await session.execute(delete(BusinessProfile).where(BusinessProfile.telegram_id == telegram_id))
            await session.commit()
    except Exception as e:
        logger.warning("_reset_db_session failed: %s", e)


async def _ensure_db_session(telegram_id: int, biz_conn_id: str | None) -> None:
    """Создать BusinessSession в БД если ещё не существует (нужно для напоминаний)."""
    if not _session_maker:
        return
    try:
        from sqlalchemy import select
        from bot.business_dialog.models import BusinessSession
        async with _session_maker() as session:
            res = await session.execute(
                select(BusinessSession).where(BusinessSession.telegram_id == telegram_id)
            )
            biz_sess = res.scalar_one_or_none()
            if not biz_sess:
                biz_sess = BusinessSession(
                    telegram_id=telegram_id,
                    status="free",
                    business_connection_id=biz_conn_id or "",
                )
                session.add(biz_sess)
                await session.commit()
    except Exception as e:
        logger.warning("_ensure_db_session failed: %s", e)
