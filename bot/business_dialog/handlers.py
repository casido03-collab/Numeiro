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
    get_paid_tier, set_paid_tier,
    get_tier_msg_count, increment_tier_msg_count,
    set_last_activity,
)

_RESET_PHRASE = "сброс12"

# ─── Техподдержка ────────────────────────────────────────────────────────────

_SUPPORT_KEYWORDS = [
    # Технические проблемы
    "бот не работает", "бот не отвечает", "бот завис", "бот сломался",
    "не работает бот", "проблема с ботом", "вопрос по боту", "вопрос о боте",
    "ошибка в боте", "не могу войти", "не открывается бот",
    "подписка не работает", "подписка не активировалась", "не получил доступ",
    "не приходит ответ", "завис", "техническая проблема",
    "техподдержка", "поддержка", "numerelogia", "@numerelogia_astro_bot",
    "ваш бот", "этот бот", "в боте", "через бот",
    # Оплата и возвраты
    "оплата не прошла", "деньги списали", "деньги не вернули", "возврат денег",
    "хочу возврат", "верните деньги", "списало дважды", "не активировалось",
    # Реклама и сотрудничество
    "по рекламе", "реклама", "рекламу", "рекламный", "рекламное",
    "сотрудничество", "сотрудничать", "партнёрство", "партнерство", "партнёр",
    "предложение о сотрудничестве", "коллаборация", "интеграция",
    "хочу разместить", "хочу рекламировать", "продвижение",
    # Общие организационные вопросы (бот/живой — перехватываются отдельно)
    "администратор", "владелец", "хозяин",
    "связаться с вами", "как связаться", "контакты", "написать вам",
    "организационный вопрос", "не по теме",
]

_SUPPORT_HOLD_TEXTS = [
    "Минуту — я уточню данную информацию и дам вам точный ответ 🌙",
    "Подождите немного — я разберусь с этим вопросом и вернусь к вам ✨",
    "Сейчас уточню все детали и дам вам точный ответ 💫",
]


def _is_support_request(text: str) -> bool:
    """Определить является ли сообщение обращением в техподдержку."""
    t = text.lower()
    return any(kw in t for kw in _SUPPORT_KEYWORDS)


# ─── Вопрос про поле «Комментарий» в Tribute ─────────────────────────────────

# Статичный ответ — не требует AI-генерации
_TRIBUTE_COMMENT_REPLY = (
    "В строке «Комментарий» напишите что угодно — любое слово или фраза подойдёт "
    "🌙 Главное чтобы строка не была пустой, иначе оплата не пройдёт."
)


def _is_tribute_comment_question(text: str) -> bool:
    """Пользователь спрашивает что писать в поле комментария при оплате через Tribute."""
    t = text.lower()
    has_comment = any(kw in t for kw in ("комментарий", "коммент", "строчку", "строку", "поле"))
    has_payment = any(kw in t for kw in (
        "оплат", "tribute", "трибут", "платёж", "платеж", "платить", "платите",
        "написать", "писать", "ввести", "вводить", "заполнить", "что вписать",
    ))
    return has_comment and has_payment


# ─── Вопрос «вы бот / вы живой человек?» ─────────────────────────────────────

_HUMAN_BOT_PHRASES = [
    "вы бот", "ты бот", "это бот", "вы робот", "ты робот",
    "вы человек", "ты человек", "живой человек", "реальный человек",
    "вы живая", "ты живая", "вы живой", "ты живой",
    "нейросеть", "нейронная сеть", "искусственный интеллект",
    "chatgpt", "чатgpt", " gpt", "чат-бот", "чатбот",
    "с кем я говорю", "кто вы такая", "кто вы на самом деле",
    "вы настоящая", "ты настоящая", "вы настоящий", "ты настоящий",
    "это автоответ", "автоответчик", "отвечает программа",
]


def _is_human_bot_question(text: str) -> bool:
    """Пользователь сомневается живая ли Аиша или это бот."""
    t = text.lower()
    return any(phrase in t for phrase in _HUMAN_BOT_PHRASES)


_SUPPORT_CATEGORIES = [
    (["реклама", "рекламу", "рекламн", "сотрудничеств", "партнёр", "партнер",
      "коллаборац", "интеграц", "продвижен", "разместить"],           "📣 Реклама / сотрудничество"),
    (["оплата", "деньги", "возврат", "списал", "списало", "активировал"],   "💳 Вопрос по оплате"),
    (["бот", "подписка", "ошибка", "не работает", "не отвечает", "завис",
      "техническ", "поддержка", "техподдержка"],                             "🔧 Техническая проблема"),
    (["администратор", "владелец", "контакты", "связаться"],                  "❓ Организационный вопрос"),
]


def _support_category(text: str) -> str:
    t = text.lower()
    for keywords, label in _SUPPORT_CATEGORIES:
        if any(kw in t for kw in keywords):
            return label
    return "📩 Входящее обращение"


# Фразы для повтора вопроса текущей стадии после ответа на «вы бот?»
_STAGE_REPROMPT = {
    "collecting_name":       "Так как же вас зовут, душа моя? 🌙",
    "collecting_birth_date": "Напишите дату рождения: например, 15.03.1990 ✨",
    "collecting_city":       "В каком городе вы живёте? 🌙",
    "collecting_problem":    "Расскажите — что сейчас тревожит больше всего? ✨",
}


async def _handle_human_bot_question(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    stage: str = "",
) -> None:
    """Короткий AI-ответ — Аиша даёт понять, что она живой человек.
    Затем повторяет вопрос текущей стадии чтобы диалог не съехал."""
    profile = await get_profile(telegram_id)
    name    = profile.get("name", "")
    name_hint = f"Имя клиента: {name}." if name else ""

    reply = await generate_business(
        AISHA_FREE_PROMPT,
        f"Клиент спрашивает — живой ли ты человек или это бот, программа, нейросеть.\n\n"
        f"Ответь ОЧЕНЬ коротко — ровно 1–2 предложения. "
        f"Дай понять что ты настоящая живая бабушка Аиша — реальный человек. "
        f"Говори тепло, с лёгкой иронией, без лишних слов. Обращайся на вы. "
        f"Никаких упоминаний технологий, ИИ или алгоритмов — только человеческое. "
        f"ВАЖНО: НЕ задавай никакого вопроса в конце — только подтверди что ты живая. "
        f"{name_hint}",
        complexity="simple",
        max_tokens=60,
    )
    await typing_short(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, reply, biz_conn_id)

    # Повторить вопрос текущей стадии — иначе пользователь отвечает на вопрос бота,
    # и следующее сообщение воспринимается как имя / дата / город
    reprompt = _STAGE_REPROMPT.get(stage)
    if reprompt:
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, reprompt, biz_conn_id)


async def _notify_admin_day_limit(bot: Bot, telegram_id: int, day_count: int) -> None:
    """Уведомить админов когда пользователь достиг дневного лимита AI-вызовов."""
    from config import settings
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    admin_ids = settings.admin_ids_list
    if not admin_ids:
        return
    profile  = await get_profile(telegram_id)
    name     = profile.get("name") or "Гость"
    username = profile.get("username", "")
    username_str = f" @{username}" if username else ""
    msg = (
        f"⚠️ Дневной лимит AI\n\n"
        f"👤 {name}{username_str} (tg_id: {telegram_id})\n"
        f"💬 Использовано сообщений сегодня: {day_count}\n\n"
        f"Проверьте диалог. Если клиент реальный — расширьте лимит командой:\n"
        f"/unlimit {telegram_id} 50"
    )
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, msg, parse_mode=None)
        except Exception as e:
            logger.warning("day_limit notify failed for admin %s: %s", admin_id, e)


async def _notify_admins(bot: Bot, telegram_id: int, name: str, text: str, username: str | None = None) -> None:
    """Уведомить всех админов о поступившем обращении в поддержку."""
    from config import settings
    admin_ids = settings.admin_ids_list
    if not admin_ids:
        logger.warning("ADMIN_IDS не настроен — уведомление не отправлено")
        return

    category = _support_category(text)
    username_str = f" @{username}" if username else ""
    msg = (
        f"🔔 {category}\n\n"
        f"👤 {name}{username_str} (tg_id: {telegram_id})\n\n"
        f"💬 {text}\n\n"
        f"Подключитесь к чату и ответьте вручную."
    )
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, msg, parse_mode=None)
        except Exception as e:
            logger.warning("admin notify failed for %s: %s", admin_id, e)

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

_CLOSING_PHRASES = [
    "спасибо", "благодарю", "благодарен", "благодарна", "понял", "поняла",
    "понятно", "всё ясно", "все ясно", "ясно", "окей", "ок", "ok",
    "ладно", "договорились", "пока", "до свидания", "всего доброго",
    "хорошо", "всё понятно", "всё хорошо", "все хорошо",
]


def _wants_to_pay(text: str) -> bool:
    """Определить хочет ли пользователь перейти к оплате."""
    t = text.lower().strip()
    return any(phrase in t for phrase in _PAYMENT_READY)


def _detect_gender(name: str) -> str:
    """Определить пол по имени (эвристика по окончанию)."""
    n = name.strip().lower()
    if n.endswith(('а', 'я')):
        return 'female'
    return 'male'


def _is_closing(text: str) -> bool:
    """Определить завершает ли пользователь разговор."""
    t = text.lower().strip()
    # Только короткие фразы — длинный ответ не считается прощанием
    return len(t) < 40 and any(phrase in t for phrase in _CLOSING_PHRASES)


_PRE_QUESTION_PHRASES = [
    "у меня есть вопрос", "у меня ещё есть вопрос", "у меня еще есть вопрос",
    "ещё один вопрос", "еще один вопрос", "можно спросить", "можно задать",
    "хочу спросить", "хочу задать вопрос", "можно ещё", "можно еще",
    "есть ещё", "есть еще", "хочу уточнить", "можно уточнить",
]

_META_SERVICE_PHRASES = [
    "можно сделать два", "два разбора", "оплатить сразу за два",
    "как это работает", "что входит", "что будет", "как долго",
    "сколько займёт", "сколько займет", "сколько стоит", "ссылка работает",
    "как оплатить", "где оплатить",
]


def _is_pre_question(text: str) -> bool:
    """Мета-вопрос или попутная реплика — не тратит follow-up слот."""
    t = text.lower().strip()
    # Очень короткие реплики (приветствие, благодарность, ок) — не follow-up
    if len(t) < 20:
        return True
    # Фразы-анонсы типа "у меня есть вопрос"
    if any(phrase in t for phrase in _PRE_QUESTION_PHRASES):
        return True
    # Вопросы об услуге/сервисе, а не о ситуации клиента
    if any(phrase in t for phrase in _META_SERVICE_PHRASES):
        return True
    return False


def _tier_timing_hint(tier_key: str) -> str:
    """Текстовое описание сроков выполнения тира для подстановки в промпт."""
    tier = get_tier(tier_key)
    days = tier.get("days")
    if days is None:
        return "сразу после оплаты — в течение нескольких минут"
    elif days == 1:
        return "в течение одного дня"
    elif days == 3:
        return "в течение трёх дней"
    else:
        return f"в течение {days} дней"


from bot.business_dialog.typing_simulation import (
    typing_short, typing_medium, typing_long, typing_deflect, typing_for_text
)
from bot.business_dialog.anti_free_chat import get_deflect_message, FREE_MSG_LIMIT
from bot.business_dialog.ai_router import detect_intent, get_product_name
from bot.business_dialog.services import generate_business
from bot.business_dialog.prompts import (
    AISHA_FREE_PROMPT, AISHA_FOLLOWUP_PROMPT, AISHA_PITCH_PROMPT,
    AISHA_ACCOMPANIMENT_PROMPT,
)
from bot.business_dialog.tribute_flow import payment_keyboard, return_payment_keyboard, TRIBUTE_PRICE
from bot.business_dialog.upsell import get_tier, tier_link, upsell_bridge, is_accompaniment
from bot.business_dialog.validators import (
    validate_name, NAME_ERRORS,
    validate_birth_date, BIRTH_DATE_ERRORS,
    validate_city, CITY_ERRORS,
)

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
    username    = message.from_user.username

    # ── Нетекстовые сообщения (стикеры, фото, голос и т.д.) ─────────────────
    if not text:
        return  # молча игнорируем — не тратим AI

    # ── Rate limiting для business-сообщений (RateLimitMiddleware не покрывает) ─
    from bot.services.cache import rate_limit_check, get_redis
    from datetime import date
    # 1. Не более 3 сообщений за 10 секунд
    if not await rate_limit_check(telegram_id, "biz_10s", 3, 10):
        return  # тихо игнорируем спам
    # 2. Не более 15 сообщений за 60 секунд
    if not await rate_limit_check(telegram_id, "biz_min", 15, 60):
        return
    # 3. Дневной лимит AI-вызовов (по умолчанию 120, admin может расширить)
    today       = date.today().isoformat()
    day_key     = f"biz_day:{telegram_id}:{today}"
    r           = await get_redis()
    day_count   = await r.incr(day_key)
    if day_count == 1:
        await r.expire(day_key, 86400)

    # Персональный лимит (admin мог расширить командой /unlimit)
    user_limit_raw = await r.get(f"biz_day_limit:{telegram_id}:{today}")
    user_limit     = int(user_limit_raw) if user_limit_raw else 120

    if day_count > user_limit:
        # Уведомить admin один раз при первом превышении
        notif_key = f"biz_day_notif:{telegram_id}:{today}"
        first_hit = await r.set(notif_key, "1", nx=True, ex=86400)
        if first_hit:
            await _notify_admin_day_limit(bot, telegram_id, day_count)
        return  # тихо игнорируем

    # Трекаем активность (для планировщика напоминаний)
    await set_last_activity(telegram_id)

    # Всегда сохраняем актуальный business_connection_id
    if biz_conn_id:
        await store_biz_conn(telegram_id, biz_conn_id)

    # ── Минимальная длина для осмысленного ответа ────────────────────────────
    # Одиночные символы/смайлы в платных стадиях не генерируем AI-ответ
    stage_now = await get_biz_stage(telegram_id)
    if len(text) < 2 and stage_now in (
        "waiting_payment", "waiting_upsell", "accompaniment", "followup"
    ):
        return

    # Кодовая фраза сброса сессии (для тестирования)
    if text.lower() == _RESET_PHRASE:
        await reset_session(telegram_id)
        await _reset_db_session(telegram_id)
        await _send(bot, chat_id, "🔄 Сессия сброшена. Пишите — начнём заново.", biz_conn_id)
        return

    stage = stage_now  # уже получен выше
    logger.info("business_msg tid=%s stage=%s text=%.40s", telegram_id, stage, text)

    # ── Вопрос про поле «Комментарий» в Tribute — статичный ответ, без AI ──────
    if _is_tribute_comment_question(text):
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, _TRIBUTE_COMMENT_REPLY, biz_conn_id)
        return

    # ── Вопрос «вы бот / живой человек?» — короткий AI-ответ, Аиша живая ──────
    if _is_human_bot_question(text):
        await _handle_human_bot_question(bot, chat_id, telegram_id, biz_conn_id, stage)
        return

    # Детект техподдержки — работает на любом этапе диалога
    if _is_support_request(text) and stage not in ("support",):
        await _handle_support(bot, chat_id, telegram_id, biz_conn_id, text, stage, username)
        return

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
        await _stage_waiting_payment(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "paid":
        await _send(bot, chat_id, f"Душа моя {_emo()} Я уже смотрю вашу ситуацию. Совсем скоро…", biz_conn_id)
    elif stage == "followup":
        await _stage_followup(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "accompaniment":
        await _stage_accompaniment(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "waiting_upsell":
        await _stage_waiting_upsell(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "completed":
        await _stage_completed(bot, chat_id, telegram_id, biz_conn_id)
    elif stage == "support":
        await _stage_support(bot, chat_id, telegram_id, biz_conn_id, text, username)


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

_UPSELL_PAYMENT_TEXTS = [
    "✨ «{p}» — {price} ₽\n\nОплатите — и я немедленно продолжу {e}",
    "✨ «{p}» — {price} ₽\n\nОдна кнопка — и мы идём дальше {e}",
    "✨ «{p}» — {price} ₽\n\nПосле оплаты сразу приступлю {e}",
]


_CLOSING_PIVOT_TEXTS = [
    "Рада была поговорить с вами {e}\n\nЕсть кое-что, что я ещё не успела сказать — в вашей ситуации есть линии, которые стоит посмотреть глубже. Если интересно — могу сделать это прямо сейчас.",
    "Подождите {e}\n\nЯ вижу в вашей ситуации кое-что важное — то, о чём мы пока не говорили. Хотите, я посмотрю это подробнее?",
    "Прежде чем вы уйдёте {e}\n\nВ том, что вы рассказали, есть момент, который требует внимания. Я могу посмотреть его для вас — спокойно и полностью.",
    "Одну минуту {e}\n\nВ вашей ситуации есть нить, которую я только начала видеть. Было бы жаль её не рассмотреть — если хотите, я могу сделать это сейчас.",
]


async def _send_closing_pivot(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    profile: dict,
) -> None:
    """Когда клиент прощается — мягко удержать и предложить углублённый разбор."""
    pivot = random.choice(_CLOSING_PIVOT_TEXTS).format(e=_emo())
    await typing_for_text(bot, chat_id, biz_conn_id, pivot)
    await _send(bot, chat_id, pivot, biz_conn_id)

    # Через паузу — полный оффер
    await typing_long(bot, chat_id, biz_conn_id)
    await _send_payment_offer(bot, chat_id, telegram_id, biz_conn_id, profile)


async def _send_payment_offer(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    profile: dict, tier_key: str = "t190",
) -> None:
    """Три сообщения с паузами: тизер → мягкий переход → счёт с кнопкой."""
    tier      = get_tier(tier_key)
    price     = tier.get("price", TRIBUTE_PRICE)
    prod_name = profile.get("product_name") or tier.get("name", "Разбор ситуации")
    context   = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
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
        e=_emo(), p=prod_name, price=price
    )
    await typing_medium(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, payment_text, biz_conn_id, reply_markup=payment_keyboard(tier_key))

    # (стадия и payment_offered уже выставлены в начале функции)


# ─── Апсейл на следующий тир ─────────────────────────────────────────────────

async def _offer_next_upsell(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    current_tier: str,
) -> None:
    """Предложить переход к следующему тиру после завершения текущего."""
    tier          = get_tier(current_tier)
    next_tier_key = tier.get("next_tier")

    if not next_tier_key:
        # Финальный тир — завершаем красиво
        await set_biz_stage(telegram_id, "completed")
        closing = random.choice([
            f"Вы прошли весь путь {_emo()} Это редко — и это очень ценно.",
            f"Наша работа стала по-настоящему глубокой {_emo()} Спасибо за доверие.",
            f"Это было важное путешествие, душа моя {_emo()} Берегите себя.",
        ])
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, closing, biz_conn_id)
        return

    next_tier = get_tier(next_tier_key)
    price     = next_tier.get("price", 0)
    name      = next_tier.get("name", "")

    # Переводим в режим ожидания апсейла
    await set_biz_stage(telegram_id, "waiting_upsell")
    await store_profile_field(telegram_id, "next_tier", next_tier_key)

    # Мостик-апсейл (атмосферный текст перехода)
    bridge = upsell_bridge(next_tier_key, _emo())
    if bridge:
        await typing_for_text(bot, chat_id, biz_conn_id, bridge)
        await _send(bot, chat_id, bridge, biz_conn_id)
        await typing_medium(bot, chat_id, biz_conn_id)

    # Предложение следующего тира с кнопкой
    offer = random.choice(_UPSELL_PAYMENT_TEXTS).format(
        e=_emo(), p=name, price=price
    )
    await _send(bot, chat_id, offer, biz_conn_id, reply_markup=payment_keyboard(next_tier_key))


# ─── Режим сопровождения (t1990, t4990, t9900) ───────────────────────────────

async def _stage_accompaniment(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str,
) -> None:
    """Режим личного наблюдения — живые ответы с историей, мягкий лимит сообщений."""
    paid_tier = await get_paid_tier(telegram_id) or "t1990"
    tier      = get_tier(paid_tier)
    msg_soft_limit = tier.get("msg_soft_limit")

    # Счётчик сообщений в текущем тире
    msg_count = await get_tier_msg_count(telegram_id)

    # Достигли мягкого лимита — предлагаем следующий тир
    if msg_soft_limit and msg_count >= msg_soft_limit:
        await _offer_next_upsell(bot, chat_id, telegram_id, biz_conn_id, paid_tier)
        return

    profile      = await get_profile(telegram_id)
    history      = await get_history(telegram_id)
    history_text = format_history(history)

    context = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
        "tier":       paid_tier,
        "msg_count":  msg_count,
    }, ensure_ascii=False)

    await append_history(telegram_id, "user", text)

    response = await generate_business(
        AISHA_ACCOMPANIMENT_PROMPT,
        f"ИСТОРИЯ ПЕРЕПИСКИ:\n{history_text}\n\n"
        f"СООБЩЕНИЕ КЛИЕНТА: {text}\n\n"
        f"Данные: {context}\n\nОбращайся на вы.",
        complexity="medium",
        max_tokens=400,
    )
    await append_history(telegram_id, "aisha", response)
    await increment_tier_msg_count(telegram_id)

    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)


# ─── Ожидание оплаты апсейла ─────────────────────────────────────────────────

async def _stage_waiting_upsell(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str = "",
) -> None:
    """Пользователь написал пока ждём оплаты следующего тира — отвечаем по смыслу, без кнопки.
    Кнопка вернётся только через 1 час неактивности (планировщик напоминаний)."""
    profile       = await get_profile(telegram_id)
    next_tier_key = profile.get("next_tier", "t490")
    timing        = _tier_timing_hint(next_tier_key)

    if text:
        context = json.dumps({
            "name":    profile.get("name", ""),
            "gender":  profile.get("gender", "unknown"),
            "problem": profile.get("problem", ""),
        }, ensure_ascii=False)
        reply = await generate_business(
            AISHA_FREE_PROMPT,
            f"Клиент задаёт вопрос: «{text}»\n\n"
            f"Ответь ОДНИМ коротким предложением (максимум 15 слов) по смыслу. "
            f"Не упоминай цену или слово 'оплата'. Обращайся на вы. "
            f"НЕ задавай вопросов в конце, НЕ добавляй концовку-триггер — просто ответь и всё.\n\n"
            f"ВАЖНО: если клиент спрашивает о времени или сроках выполнения — ответь точно: {timing}. "
            f"Никогда не придумывай сроки.\n\n"
            f"ВАЖНО: если клиент спрашивает о ссылке на оплату (как долго работает, истекает ли) — "
            f"отвечай что ссылка работает в любой момент, без ограничений по времени, "
            f"буду ждать вашего шага.\n\nДанные: {context}",
            complexity="simple",
            max_tokens=50,
        )
        await typing_for_text(bot, chat_id, biz_conn_id, reply)
        await _send(bot, chat_id, reply, biz_conn_id)
    # Кнопку НЕ повторяем — она придёт через планировщик после 1 часа тишины


# ─── Этапы диалога ────────────────────────────────────────────────────────────

async def _handle_support(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    text: str, prev_stage: str, username: str | None = None,
) -> None:
    """Первичная обработка обращения в техподдержку."""
    profile = await get_profile(telegram_id)
    name = profile.get("name") or "Гость"

    # Сохраняем предыдущую стадию чтобы можно было вернуться
    await store_profile_field(telegram_id, "pre_support_stage", prev_stage)
    await set_biz_stage(telegram_id, "support")

    # Ответ пользователю
    hold = random.choice(_SUPPORT_HOLD_TEXTS)
    await typing_short(bot, chat_id, biz_conn_id)
    await _send(bot, chat_id, hold, biz_conn_id)

    # Уведомление админам
    await _notify_admins(bot, telegram_id, name, text, username)


async def _stage_support(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
    text: str, username: str | None = None,
) -> None:
    """Режим ожидания: пересылаем сообщения админу, пользователю — hold-ответ."""
    profile = await get_profile(telegram_id)
    name = profile.get("name") or "Гость"

    # Пересылаем новое сообщение админам
    await _notify_admins(bot, telegram_id, name, text, username)

    # Пользователю — краткое подтверждение
    await typing_short(bot, chat_id, biz_conn_id)
    await _send(
        bot, chat_id,
        "Я уточняю — пожалуйста, немного подождите 🌙",
        biz_conn_id,
    )


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
    ok, result = validate_name(text)
    if not ok:
        error_msg = NAME_ERRORS.get(result, f"Напишите своё имя {_emo()}")
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, error_msg, biz_conn_id)
        return

    name   = result
    gender = _detect_gender(name)
    await store_profile_field(telegram_id, "name", name)
    await store_profile_field(telegram_id, "gender", gender)
    await set_biz_stage(telegram_id, "collecting_birth_date")

    response = (
        f"Как хорошо, {name} {_emo()} Чтобы я смогла посмотреть вашу ситуацию глубже — "
        f"скажите, когда вы родились?\nНапишите дату вот так: 15.03.1990"
    )
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)


async def _stage_birth_date(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    ok, result = validate_birth_date(text)
    if not ok:
        error_msg = BIRTH_DATE_ERRORS.get(result, f"Напишите дату рождения вот так: 15.03.1990 {_emo()}")
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, error_msg, biz_conn_id)
        return

    await store_profile_field(telegram_id, "birth_date", result)
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
    ok, result = validate_city(text)
    if not ok:
        error_msg = CITY_ERRORS.get(result, f"Напишите название города {_emo()}")
        await typing_short(bot, chat_id, biz_conn_id)
        await _send(bot, chat_id, error_msg, biz_conn_id)
        return

    await store_profile_field(telegram_id, "city", result)
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
        "gender":     profile.get("gender", "unknown"),
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
    # Если пользователь выражает готовность оплатить — плавно переходим к оплате
    if _wants_to_pay(text):
        profile = await get_profile(telegram_id)
        await _send_payment_offer(bot, chat_id, telegram_id, biz_conn_id, profile)
        return

    # Если пользователь прощается/благодарит — не отпускаем, предлагаем углублённый разбор
    if _is_closing(text):
        profile = await get_profile(telegram_id)
        await _send_closing_pivot(bot, chat_id, telegram_id, biz_conn_id, profile)
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
        "gender":     profile.get("gender", "unknown"),
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


async def _stage_waiting_payment(
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str = "",
) -> None:
    """Пользователь задаёт вопрос пока не оплатил — отвечаем по смыслу, без кнопки.
    Кнопка вернётся только через 1 час неактивности (планировщик напоминаний)."""
    profile = await get_profile(telegram_id)
    context = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
    }, ensure_ascii=False)

    if text:
        timing = _tier_timing_hint("t190")
        reply = await generate_business(
            AISHA_FREE_PROMPT,
            f"Клиент уже получил предложение разбора и задаёт дополнительный вопрос: «{text}»\n\n"
            f"Ответь ОДНИМ коротким предложением (максимум 15 слов) точно по смыслу вопроса. "
            f"Не называй цену и не упоминай слово 'оплата'. Обращайся на вы. "
            f"НЕ задавай вопросов в конце, НЕ добавляй концовку-триггер — просто ответь и всё.\n\n"
            f"ВАЖНО: если клиент спрашивает о времени или сроках выполнения — ответь точно: {timing}. "
            f"Никогда не говори 'несколько дней' — это неправда.\n\n"
            f"ВАЖНО: если клиент спрашивает о ссылке на оплату (как долго работает, истекает ли, "
            f"когда действует) — отвечай что ссылка работает в любой момент, без ограничений по времени, "
            f"буду ждать вашего шага. Не говори что ссылка истекает или ограничена по времени.\n\n"
            f"Данные: {context}",
            complexity="simple",
            max_tokens=50,
        )
        await typing_for_text(bot, chat_id, biz_conn_id, reply)
        await _send(bot, chat_id, reply, biz_conn_id)
    # Кнопку НЕ повторяем — она придёт через планировщик после 1 часа тишины


async def _stage_followup(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    """Уточняющие вопросы после платной консультации.

    Различаем два типа сообщений:
    - Мета/попутные реплики (анонс вопроса, благодарность, сервисный вопрос)
      → краткий AI-ответ БЕЗ траты follow-up слота
    - Реальный follow-up вопрос по ситуации
      → полный ответ, тратит слот
    """
    profile   = await get_profile(telegram_id)
    paid_tier = await get_paid_tier(telegram_id) or "t190"
    tier      = get_tier(paid_tier)

    context_base = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
    }, ensure_ascii=False)

    # ── Мета-вопрос / попутная реплика — не тратит слот ──────────────────────
    if _is_pre_question(text):
        left = await get_followup_left(telegram_id)
        quick = await generate_business(
            AISHA_FOLLOWUP_PROMPT,
            f"Клиент написал попутную реплику или анонс вопроса: «{text}»\n\n"
            f"Ответь очень коротко (1 предложение), по смыслу. "
            f"Если это анонс вопроса — пригласи задать его. "
            f"Если благодарность — тепло прими. "
            f"НЕ задавай встречных вопросов. Обращайся на вы.\n\n"
            f"Данные: {context_base}",
            complexity="simple",
            max_tokens=60,
        )
        await typing_for_text(bot, chat_id, biz_conn_id, quick)
        await _send(bot, chat_id, quick, biz_conn_id)
        return  # слот НЕ тратится

    # ── Реальный follow-up вопрос — тратит слот ───────────────────────────────
    left = await decrement_followup(telegram_id)

    context = json.dumps({
        "name":           profile.get("name", ""),
        "gender":         profile.get("gender", "unknown"),
        "birth_date":     profile.get("birth_date", ""),
        "problem":        profile.get("problem", ""),
        "tier":           tier.get("name", ""),
        "followups_left": left,
    }, ensure_ascii=False)

    await append_history(telegram_id, "user", text)
    response = await generate_business(
        AISHA_FOLLOWUP_PROMPT,
        f"Уточняющий вопрос после консультации: {text}\n\nДанные: {context}\n\nОбращайся на вы.",
        complexity="medium",
        max_tokens=300,
    )
    await append_history(telegram_id, "aisha", response)
    await typing_for_text(bot, chat_id, biz_conn_id, response)
    await _send(bot, chat_id, response, biz_conn_id)

    if left == 0:
        # Follow-up вопросы закончились → предлагаем следующий тир
        await typing_short(bot, chat_id, biz_conn_id)
        await _offer_next_upsell(bot, chat_id, telegram_id, biz_conn_id, paid_tier)


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
