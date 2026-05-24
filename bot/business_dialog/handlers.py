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
    # Общие организационные вопросы
    "кто вы", "кто это", "это настоящий человек", "вы живой", "вы человек",
    "с кем я говорю", "это бот", "администратор", "владелец", "хозяин",
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


_SUPPORT_CATEGORIES = [
    (["реклама", "рекламу", "рекламн", "сотрудничеств", "партнёр", "партнер",
      "коллаборац", "интеграц", "продвижен", "разместить"],           "📣 Реклама / сотрудничество"),
    (["оплата", "деньги", "возврат", "списал", "списало", "активировал"],   "💳 Вопрос по оплате"),
    (["бот", "подписка", "ошибка", "не работает", "не отвечает", "завис",
      "техническ", "поддержка", "техподдержка"],                             "🔧 Техническая проблема"),
    (["кто вы", "живой", "человек", "с кем я", "администратор",
      "владелец", "контакты", "связаться"],                                  "❓ Организационный вопрос"),
]


def _support_category(text: str) -> str:
    t = text.lower()
    for keywords, label in _SUPPORT_CATEGORIES:
        if any(kw in t for kw in keywords):
            return label
    return "📩 Входящее обращение"


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
        await _stage_waiting_payment(bot, chat_id, telegram_id, biz_conn_id)
    elif stage == "paid":
        await _send(bot, chat_id, f"Душа моя {_emo()} Я уже смотрю вашу ситуацию. Совсем скоро…", biz_conn_id)
    elif stage == "followup":
        await _stage_followup(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "accompaniment":
        await _stage_accompaniment(bot, chat_id, telegram_id, biz_conn_id, text)
    elif stage == "waiting_upsell":
        await _stage_waiting_upsell(bot, chat_id, telegram_id, biz_conn_id)
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
    bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None,
) -> None:
    """Пользователь написал пока ждём оплаты следующего тира — напоминаем."""
    profile       = await get_profile(telegram_id)
    next_tier_key = profile.get("next_tier", "t490")
    tier          = get_tier(next_tier_key)
    name          = tier.get("name", "")
    price         = tier.get("price", 0)

    await typing_deflect(bot, chat_id, biz_conn_id)
    deflect = await get_deflect_message(telegram_id)
    await _send(bot, chat_id, deflect, biz_conn_id)

    await typing_short(bot, chat_id, biz_conn_id)
    await _send(
        bot, chat_id,
        f"Душа моя, я оставила «{name}» открытым для вас {_emo()} Когда будете готовы — просто нажмите кнопку.",
        biz_conn_id,
        reply_markup=payment_keyboard(next_tier_key),
    )


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
    if not text:
        await _send(bot, chat_id, f"Напишите своё имя {_emo()}", biz_conn_id)
        return

    name = text.strip().split()[0].capitalize()
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
        reply_markup=return_payment_keyboard("t190"),
    )


async def _stage_followup(bot: Bot, chat_id: int, telegram_id: int, biz_conn_id: str | None, text: str) -> None:
    """Уточняющие вопросы после платной консультации."""
    left = await decrement_followup(telegram_id)

    profile    = await get_profile(telegram_id)
    paid_tier  = await get_paid_tier(telegram_id) or "t190"
    tier       = get_tier(paid_tier)
    tier_name  = tier.get("name", "")

    context = json.dumps({
        "name":           profile.get("name", ""),
        "gender":         profile.get("gender", "unknown"),
        "birth_date":     profile.get("birth_date", ""),
        "problem":        profile.get("problem", ""),
        "tier":           tier_name,
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
