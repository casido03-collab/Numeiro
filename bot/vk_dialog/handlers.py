"""FSM-обработчики VK-диалога бабушки Аиши."""
import asyncio
import json
import logging
import random
import re
import time
from datetime import date
from pathlib import Path

from bot.vk_dialog.session_manager import (
    get_stage, set_stage,
    get_profile, store_field,
    get_free_count, increment_free_count,
    get_followup_left, set_followup_left, decrement_followup,
    get_paid_tier, set_paid_tier, set_payment_offered,
    get_tier_msg_count, increment_tier_msg_count,
    append_history, get_history, format_history,
    set_last_activity, reset_session, register_user,
)
from bot.business_dialog.services import generate_business
from bot.business_dialog.prompts import (
    AISHA_FREE_PROMPT, AISHA_FOLLOWUP_PROMPT, AISHA_PITCH_PROMPT,
    AISHA_ACCOMPANIMENT_PROMPT, AISHA_TAROT_BUSINESS_PROMPT,
)
from bot.business_dialog.upsell import get_tier, upsell_bridge, is_accompaniment
from bot.business_dialog.handlers import (
    _tier_timing_hint,
    _is_support_request, _is_payment_link_issue, _is_human_bot_question,
    _VPN_REPLIES, _SUPPORT_HOLD_TEXTS, _STAGE_REPROMPT,
)
from bot.business_dialog.ai_router import detect_intent, get_product_name
from bot.business_dialog.validators import (
    validate_name, NAME_ERRORS,
    validate_birth_date, BIRTH_DATE_ERRORS,
    validate_city, CITY_ERRORS,
)
from bot.business_dialog.timezone_utils import get_city_tz_offset
from bot.business_dialog.anti_free_chat import get_deflect_message, FREE_MSG_LIMIT
from bot.business_dialog.utils import followup_invite
from bot.vk_dialog.payments import create_payment_link

logger = logging.getLogger(__name__)

_RESET_PHRASE = "сброс12"
_ESOTERIC_EMOJIS = ["🌙", "✨", "💫", "🔮", "🌟", "⭐", "🌌", "💎"]
_TAROT_ASSETS = Path(__file__).parent.parent.parent / "assets" / "tarot"
_T990_WAIT_SECONDS = 480

_MAJOR_ARCANA = [
    ("00_fool",             "Шут",              "0 — Шут"),
    ("01_magician",         "Маг",              "I — Маг"),
    ("02_high_priestess",   "Верховная Жрица",  "II — Верховная Жрица"),
    ("03_empress",          "Императрица",      "III — Императрица"),
    ("04_emperor",          "Император",        "IV — Император"),
    ("05_hierophant",       "Иерофант",         "V — Иерофант"),
    ("06_lovers",           "Влюблённые",       "VI — Влюблённые"),
    ("07_chariot",          "Колесница",        "VII — Колесница"),
    ("08_strength",         "Сила",             "VIII — Сила"),
    ("09_hermit",           "Отшельник",        "IX — Отшельник"),
    ("10_wheel_of_fortune", "Колесо Фортуны",   "X — Колесо Фортуны"),
    ("11_justice",          "Справедливость",   "XI — Справедливость"),
    ("12_hanged_man",       "Повешенный",       "XII — Повешенный"),
    ("13_death",            "Смерть",           "XIII — Смерть"),
    ("14_temperance",       "Умеренность",      "XIV — Умеренность"),
    ("15_devil",            "Дьявол",           "XV — Дьявол"),
    ("16_tower",            "Башня",            "XVI — Башня"),
    ("17_star",             "Звезда",           "XVII — Звезда"),
    ("18_moon",             "Луна",             "XVIII — Луна"),
    ("19_sun",              "Солнце",           "XIX — Солнце"),
    ("20_judgement",        "Суд",              "XX — Суд"),
    ("21_world",            "Мир",              "XXI — Мир"),
]


def _emo() -> str:
    return random.choice(_ESOTERIC_EMOJIS)


# Имена которые используются для обоих полов — определяем по VK профилю
_AMBIGUOUS_NAMES = {
    "саша", "женя", "валя", "слава", "шура", "никита",
    "дениса", "илья", "лёша", "лёша", "сеня", "андрей",
}


def _detect_gender(name: str, vk_sex: int = 0) -> str:
    """Определить пол по имени или VK sex (1=female, 2=male)."""
    if vk_sex == 1:
        return "female"
    if vk_sex == 2:
        return "male"
    n = name.strip().lower()
    if n in _AMBIGUOUS_NAMES:
        return "unknown"  # нейтральное обращение
    return "female" if n.endswith(("а", "я")) else "male"


def _is_closing(text: str) -> bool:
    _CLOSING = ["спасибо", "благодарю", "понял", "поняла", "понятно", "ясно",
                "окей", "ок", "пока", "до свидания", "хорошо"]
    t = text.lower().strip()
    if len(t) >= 40:
        return False
    # Проверяем целые слова — «покой» не должно совпадать с «ок»
    for phrase in _CLOSING:
        pattern = r'(?<![а-яёa-z])' + re.escape(phrase) + r'(?![а-яёa-z])'
        if re.search(pattern, t):
            return True
    return False


def _wants_to_pay(text: str) -> bool:
    _PAY = ["готова", "готов", "оплачу", "хочу оплатить", "давайте", "согласна",
            "согласен", "берём", "закажу", "как оплатить"]
    t = text.lower().strip()
    return any(p in t for p in _PAY)


_DISSATISFACTION_SIGNALS = [
    "не получила", "не получил", "зря заплатила", "зря заплатил",
    "за те деньги", "ничего конкретного", "ничего нового", "общие слова",
    "разочарована", "разочарован", "обидно", "без толку", "бесполезно",
    "не помогло", "обманули", "развод", "ожидала больше",
]


def _is_dissatisfied(text: str) -> bool:
    if len(text) < 8:
        return False
    t = text.lower()
    return any(s in t for s in _DISSATISFACTION_SIGNALS)


# ─── Утилиты форматирования ───────────────────────────────────────────────────

def _strip_markdown(text: str) -> str:
    """Убрать Markdown-разметку — VK её не рендерит, она показывается как символы."""
    # **жирный** и __жирный__ → просто текст
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__",     r"\1", text, flags=re.DOTALL)
    # *курсив* и _курсив_ → просто текст
    text = re.sub(r"\*(.+?)\*",     r"\1", text, flags=re.DOTALL)
    text = re.sub(r"_(.+?)_",       r"\1", text, flags=re.DOTALL)
    # `код` → просто текст
    text = re.sub(r"`(.+?)`",       r"\1", text, flags=re.DOTALL)
    # ### Заголовки → убрать #
    text = re.sub(r"^#{1,6}\s+",    "",    text, flags=re.MULTILINE)
    return text.strip()


_VK_MAX_LEN = 4000  # VK лимит — 4096, оставляем запас


def _split_message(text: str) -> list[str]:
    """Разбить текст на части ≤4000 символов по абзацам."""
    if len(text) <= _VK_MAX_LEN:
        return [text]

    parts   = []
    current = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        para_len = len(paragraph) + 2  # +2 за \n\n
        if current_len + para_len > _VK_MAX_LEN and current:
            parts.append("\n\n".join(current))
            current     = [paragraph]
            current_len = para_len
        else:
            current.append(paragraph)
            current_len += para_len

    if current:
        parts.append("\n\n".join(current))

    return parts or [text]


# ─── Вспомогательный отправщик + typing ──────────────────────────────────────

async def _send(api, peer_id: int, text: str) -> None:
    """Отправить сообщение в VK: очистить Markdown, разбить если длинное."""
    text = _strip_markdown(text)
    parts = _split_message(text)
    for i, part in enumerate(parts):
        try:
            await api.messages.send(
                peer_id=peer_id,
                message=part,
                random_id=random.randint(1, 2**31),
            )
        except Exception as e:
            logger.warning("VK send failed (peer=%s, part=%d): %s", peer_id, i, e)
        if len(parts) > 1 and i < len(parts) - 1:
            await asyncio.sleep(0.5)  # небольшая пауза между частями


_VK_TYPING_REFRESH = 5.0  # VK гасит индикатор через ~5 сек — обновляем чуть чаще


async def _typing(api, peer_id: int, seconds: float = 2.0) -> None:
    """Держать индикатор «печатает» ровно seconds секунд.
    Повторяет set_activity каждые 5 сек чтобы индикатор не гас."""
    elapsed = 0.0
    while elapsed < seconds:
        try:
            await api.messages.set_activity(peer_id=peer_id, type="typing")
        except Exception:
            pass
        sleep_for = min(_VK_TYPING_REFRESH, seconds - elapsed)
        await asyncio.sleep(sleep_for)
        elapsed += sleep_for


async def _typing_short(api, peer_id: int) -> None:
    """1.5–2.5 сек: системные сообщения, подтверждения."""
    await _typing(api, peer_id, random.uniform(1.5, 2.5))


async def _typing_medium(api, peer_id: int) -> None:
    """3–5 сек: средние сообщения, переходы."""
    await _typing(api, peer_id, random.uniform(3.0, 5.0))


async def _typing_long(api, peer_id: int) -> None:
    """6–10 сек: длинные ответы, AI-генерация."""
    await _typing(api, peer_id, random.uniform(6.0, 10.0))


async def _typing_deflect(api, peer_id: int) -> None:
    """8–18 сек: deflect-сообщения — имитация занятости."""
    await _typing(api, peer_id, random.uniform(8.0, 18.0))


def _calc_typing_seconds(text: str) -> float:
    """Рассчитать реалистичное время набора по длине текста."""
    chars       = len(text)
    think_pause = random.uniform(1.5, 3.0)
    type_time   = chars / 4.0          # ~4 символа/сек
    total       = think_pause + type_time
    jitter      = random.uniform(0.85, 1.15)
    return min(total * jitter, 22.0)   # не дольше 22 сек


async def _typing_for_text(api, peer_id: int, text: str) -> None:
    """Задержка точно под длину текста."""
    await _typing(api, peer_id, _calc_typing_seconds(text))


# ─── Платёжная ссылка ────────────────────────────────────────────────────────

def _payment_text(tier_key: str) -> str:
    tier  = get_tier(tier_key)
    price = tier.get("price", 190)
    name  = tier.get("name", "Разбор")
    try:
        link = create_payment_link(0, tier_key)  # peer_id подставим при вызове
        return f"💎 {name} — {price} ₽\n\n{link}"
    except Exception as e:
        logger.warning("Payment link creation failed: %s", e)
        return f"💎 {name} — {price} ₽\n\nСвяжитесь с нами для оплаты."


def _make_keyboard(*labels: str, one_time: bool = True) -> str:
    """Создать JSON клавиатуры VK с текстовыми кнопками."""
    try:
        from vkbottle import Keyboard, Text, KeyboardButtonColor
        kb = Keyboard(one_time=one_time, inline=False)
        for label in labels:
            kb.add(Text(label), color=KeyboardButtonColor.SECONDARY)
        return kb.get_json()
    except Exception:
        return ""  # если vkbottle не установлен — без клавиатуры


async def _send_with_keyboard(api, peer_id: int, text: str, keyboard_json: str) -> None:
    """Отправить сообщение с клавиатурой VK."""
    text = _strip_markdown(text)
    try:
        await api.messages.send(
            peer_id=peer_id,
            message=text,
            keyboard=keyboard_json,
            random_id=random.randint(1, 2**31),
        )
    except Exception as e:
        logger.warning("VK send_with_keyboard failed (peer=%s): %s", peer_id, e)
        await _send(api, peer_id, text)  # fallback без клавиатуры


async def _remove_keyboard(api, peer_id: int, text: str) -> None:
    """Отправить сообщение и убрать клавиатуру (пустой keyboard JSON)."""
    try:
        from vkbottle import Keyboard
        empty_kb = Keyboard(one_time=False).get_json()
    except Exception:
        empty_kb = '{"one_time":false,"buttons":[]}'
    await _send_with_keyboard(api, peer_id, text, empty_kb)


async def _send_payment_offer(api, peer_id: int, uid: int, tier_key: str = "t190") -> None:
    """Тизер → переход → ссылка на оплату с кнопками VK."""
    tier  = get_tier(tier_key)
    price = tier.get("price", 190)
    name  = tier.get("name", "Разбор ситуации")

    profile = await get_profile(uid)
    context = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
        "product":    name,
    }, ensure_ascii=False)

    # Атомарная блокировка через NX — только один поток запускает оффер
    from bot.services.cache import get_redis as _get_redis
    _r = await _get_redis()
    acquired = await _r.set(f"vk:sending:{uid}", "1", nx=True, ex=60)
    if not acquired:
        return  # другой поток уже отправляет оффер этому пользователю

    await set_stage(uid, "waiting_payment")
    await set_payment_offered(uid)

    try:
        # Тизер
        teaser = await generate_business(
            AISHA_PITCH_PROMPT,
            f"Данные клиента: {context}",
            complexity="simple",
            max_tokens=90,
        )
        await _typing_medium(api, peer_id)
        await _send(api, peer_id, teaser)

        # Переход
        bridge = random.choice([
            "Но такие вещи я смотрю глубже и спокойно, чтобы ничего не упустить.\n\nЕсли хотите — я готова начать полный просмотр.",
            "Это требует тихого и внимательного взгляда — не торопясь, по всем линиям.\n\nЯ готова, если вы разрешите.",
            "Такие ситуации лучше смотреть целиком — иначе можно упустить самое важное.\n\nКогда почувствуете, что готовы — я сразу начну.",
        ])
        await _typing_medium(api, peer_id)
        await _send(api, peer_id, bridge)
    finally:
        await _r.delete(f"vk:sending:{uid}")

    # Ссылка на оплату + кнопка «Перейти к оплате»
    try:
        link = create_payment_link(uid, tier_key)
        payment_msg = f"✨ «{name}» — {price} ₽\n\nПосле оплаты приступлю сразу же {_emo()}\n\n{link}"
    except Exception as e:
        logger.error("VK payment link error: %s", e)
        payment_msg = f"✨ «{name}» — {price} ₽\n\nОплата временно недоступна — напишите нам."

    kb = _make_keyboard("✅ Оплатить", "❓ Расскажите подробнее", one_time=True)
    await _typing_medium(api, peer_id)
    if kb:
        await _send_with_keyboard(api, peer_id, payment_msg, kb)
    else:
        await _send(api, peer_id, payment_msg)


# ─── Апсейл на следующий тир ─────────────────────────────────────────────────

async def _offer_next_upsell(api, peer_id: int, uid: int, current_tier: str) -> None:
    tier          = get_tier(current_tier)
    next_tier_key = tier.get("next_tier")

    if not next_tier_key:
        await set_stage(uid, "completed")
        await _send(api, peer_id, random.choice([
            f"Вы прошли весь путь {_emo()} Это редко — и это очень ценно.",
            f"Наша работа стала по-настоящему глубокой {_emo()} Спасибо за доверие.",
        ]))
        return

    next_tier = get_tier(next_tier_key)
    price     = next_tier.get("price", 0)
    name      = next_tier.get("name", "")

    await set_stage(uid, "waiting_upsell")
    await store_field(uid, "next_tier", next_tier_key)

    # Мостик
    bridge = upsell_bridge(next_tier_key, _emo())
    if bridge:
        await _typing_medium(api, peer_id)
        await _send(api, peer_id, bridge)

    # Для t1990 — подробное описание
    if next_tier_key == "t1990":
        desc = random.choice([
            f"Позвольте объяснить, что это значит — семь дней рядом 🌟\n\n"
            f"Каждое утро в 8 часов я буду присылать вам личное послание — план на день.\n\n"
            f"В течение дня вы можете задавать мне вопросы — до 6 в день. "
            f"Я отвечу как эзотерик: с вниманием, без давления.\n\n"
            f"Семь дней живого присутствия рядом с вашей жизнью ✨",
        ])
        await _typing_medium(api, peer_id)
        await _send(api, peer_id, desc)

    # Ссылка + кнопка
    try:
        link = create_payment_link(uid, next_tier_key)
        offer = f"✨ «{name}» — {price} ₽\n\n{link}"
    except Exception as e:
        logger.error("VK upsell link error: %s", e)
        offer = f"✨ «{name}» — {price} ₽\n\nСвяжитесь с нами для оформления."

    kb = _make_keyboard("✅ Оплатить", "❓ Расскажите подробнее", one_time=True)
    await _typing_medium(api, peer_id)
    if kb:
        await _send_with_keyboard(api, peer_id, offer, kb)
    else:
        await _send(api, peer_id, offer)


# ─── Главный обработчик сообщения ─────────────────────────────────────────────

async def _handle_human_bot_question_vk(api, uid: int, stage: str) -> None:
    """Короткий AI-ответ — Аиша живой человек. Затем повторяет вопрос стадии."""
    profile   = await get_profile(uid)
    name      = profile.get("name", "")
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
        complexity="simple", max_tokens=60,
    )
    await _typing_short(api, uid)
    await _send(api, uid, reply)
    reprompt = _STAGE_REPROMPT.get(stage)
    if reprompt:
        await _typing_short(api, uid)
        await _send(api, uid, reprompt)


async def _handle_support_vk(api, uid: int, prev_stage: str) -> None:
    """Переводим в режим поддержки — шлём hold-текст."""
    await store_field(uid, "pre_support_stage", prev_stage)
    await set_stage(uid, "support")
    hold = random.choice(_SUPPORT_HOLD_TEXTS)
    await _typing_short(api, uid)
    await _send(api, uid, hold)


async def _stage_support_vk(api, uid: int) -> None:
    """Стадия support — продолжаем присылать hold-сообщения."""
    await _typing_short(api, uid)
    await _send(api, uid, "Я уточняю — пожалуйста, немного подождите 🌙")


async def handle_vk_message(api, uid: int, text: str, first_name: str = "", vk_sex: int = 0) -> None:
    """Точка входа — вызывается из router.py на каждое входящее сообщение."""
    text = text.strip()
    if not text:
        return

    await set_last_activity(uid)
    await register_user(uid)  # реестр для планировщика пушей

    stage = await get_stage(uid)
    logger.info("vk msg uid=%s stage=%s text=%.40s", uid, stage, text)

    # Сброс сессии
    if text.lower() == _RESET_PHRASE:
        await reset_session(uid)
        await _send(api, uid, "🔄 Сессия сброшена. Пишите — начнём заново.")
        return

    # Rate-limiting
    from bot.services.cache import get_redis, rate_limit_check
    if not await rate_limit_check(uid, "vk_10s", 3, 10):
        return
    if not await rate_limit_check(uid, "vk_min", 15, 60):
        return

    # Блокировка на время отправки payment offer — не перебиваем поток
    _r = await get_redis()
    if await _r.exists(f"vk:sending:{uid}"):
        return

    # Минимальная длина для осмысленного ответа на платных стадиях
    if len(text) < 2 and stage in ("waiting_payment", "waiting_upsell", "accompaniment", "followup"):
        return

    # ── Проблема с открытием ссылки — VPN подсказка ───────────────────────────
    if _is_payment_link_issue(text):
        await _typing_short(api, uid)
        await _send(api, uid, random.choice(_VPN_REPLIES))
        return

    # ── Вопрос «вы бот?» ──────────────────────────────────────────────────────
    if _is_human_bot_question(text):
        await _handle_human_bot_question_vk(api, uid, stage)
        return

    # ── Техподдержка ──────────────────────────────────────────────────────────
    if _is_support_request(text) and stage not in ("support",):
        await _handle_support_vk(api, uid, stage)
        return

    # ── Недовольство на платных стадиях ───────────────────────────────────────
    if stage in ("followup", "accompaniment", "waiting_payment", "completed") and _is_dissatisfied(text):
        await _handle_dissatisfaction(api, uid, text)
        return

    # Роутинг по стадиям
    if stage in ("new", ""):
        await _stage_new(api, uid, first_name, text, vk_sex)
    elif stage == "collecting_name":
        await _stage_name(api, uid, text)
    elif stage == "collecting_birth_date":
        await _stage_birth_date(api, uid, text)
    elif stage == "collecting_city":
        await _stage_city(api, uid, text)
    elif stage == "collecting_problem":
        await _stage_problem(api, uid, text)
    elif stage == "answered":
        await _stage_answered_vk(api, uid, text)
    elif stage == "paid_monthly":
        await _stage_paid_monthly_vk(api, uid, text)
    elif stage == "free_dialog":
        await _stage_free_dialog(api, uid, text)
    elif stage == "waiting_payment":
        await _stage_waiting_payment(api, uid, text)
    elif stage == "paid":
        await _send(api, uid, f"Душа моя {_emo()} Я уже смотрю вашу ситуацию. Совсем скоро…")
    elif stage == "followup":
        await _stage_followup(api, uid, text)
    elif stage == "accompaniment":
        await _stage_accompaniment(api, uid, text)
    elif stage == "waiting_upsell":
        await _stage_waiting_upsell(api, uid, text)
    elif stage == "t990_waiting_question":
        await _stage_t990_waiting_question(api, uid, text)
    elif stage == "t990_preparing":
        await _stage_t990_preparing(api, uid, text)
    elif stage == "completed":
        await _stage_completed(api, uid)
    elif stage == "support":
        await _stage_support_vk(api, uid)


# ─── Стадии диалога ───────────────────────────────────────────────────────────

async def _stage_new(api, uid: int, first_name: str, text: str = "", vk_sex: int = 0) -> None:
    await set_stage(uid, "collecting_name")
    if first_name:
        await store_field(uid, "vk_name_hint", first_name)
    if vk_sex:
        await store_field(uid, "vk_sex", vk_sex)  # сохраняем пол из VK профиля
    # Сохраняем первое сообщение как подсказку к проблеме
    if text and len(text) > 5:
        await store_field(uid, "first_message_hint", text[:300])
    welcome = f"Здравствуйте, душа моя {_emo()}\n\nРада, что вы написали — я обязательно посмотрю вашу ситуацию. Прежде чем начнём — скажите, как вас зовут?"
    await _typing_for_text(api, uid, welcome)
    await _send(api, uid, welcome)


async def _stage_name(api, uid: int, text: str) -> None:
    ok, result = validate_name(text)
    if not ok:
        await _typing_short(api, uid)
        await _send(api, uid, NAME_ERRORS.get(result, f"Напишите своё имя {_emo()}"))
        return
    name    = result
    profile = await get_profile(uid)
    vk_sex  = int(profile.get("vk_sex", 0) or 0)
    gender  = _detect_gender(name, vk_sex)
    await store_field(uid, "name", name)
    await store_field(uid, "gender", gender)
    await set_stage(uid, "collecting_birth_date")
    resp = (
        f"Как хорошо, {name} {_emo()} Чтобы я смогла посмотреть вашу ситуацию глубже — "
        f"скажите, когда вы родились?\nНапишите дату вот так: 15.03.1990"
    )
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)


async def _stage_birth_date(api, uid: int, text: str) -> None:
    ok, result = validate_birth_date(text)
    if not ok:
        await _typing_short(api, uid)
        await _send(api, uid, BIRTH_DATE_ERRORS.get(result, f"Напишите дату рождения вот так: 15.03.1990 {_emo()}"))
        return
    await store_field(uid, "birth_date", result)
    await set_stage(uid, "collecting_city")
    resp = f"Благодарю вас {_emo()} И последний вопрос прежде чем мы начнём — в каком городе вы живёте?"
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)


async def _stage_city(api, uid: int, text: str) -> None:
    ok, result = validate_city(text)
    if not ok:
        await _typing_short(api, uid)
        await _send(api, uid, CITY_ERRORS.get(result, f"Напишите название города {_emo()}"))
        return
    await store_field(uid, "city", result)
    tz_offset = get_city_tz_offset(result)
    await store_field(uid, "tz_offset", tz_offset)
    await set_stage(uid, "collecting_problem")
    profile = await get_profile(uid)
    name    = profile.get("name", "вы")
    gender  = profile.get("gender", "unknown")
    if gender == "female":
        adj = "хорошая"
    elif gender == "male":
        adj = "хороший"
    else:
        adj = None  # нейтральное обращение для амбигуозных имён
    intro = random.choice([
        f"{'Мой ' + adj + ' ' if adj else 'Душа моя, '}{name} {_emo()}\n\nЗадайте мне свой вопрос — я отвечу вам прямо и честно.",
        f"{name}, я здесь {_emo()}\n\nЧто вы хотите узнать? Задайте ваш вопрос.",
        f"Слышу вас, {name} {_emo()}\n\nЗадайте ваш вопрос — я отвечу.",
        f"{name}, задайте мне свой вопрос {_emo()} Я готова.",
    ])
    await _typing_for_text(api, uid, intro)
    await _send(api, uid, intro)


async def _stage_problem(api, uid: int, text: str) -> None:
    """Пользователь задал вопрос — отвечаем прямо, через 5 минут показываем оффер."""
    if not text or len(text) < 5:
        await _send(api, uid, f"Напишите ваш вопрос, душа моя {_emo()}")
        return

    await store_field(uid, "problem", text)
    await set_stage(uid, "answered")

    profile = await get_profile(uid)
    context = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "city":       profile.get("city", ""),
        "question":   text,
    }, ensure_ascii=False)

    from bot.prompts.prompts import PERSONAL_QUESTION_PROMPT
    resp = await generate_business(
        PERSONAL_QUESTION_PROMPT,
        f"Вопрос пользователя: {text}\n\nДанные: {context}",
        complexity="medium", max_tokens=350,
    )
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)

    # 1 минута с индикатором «печатает», потом оффер
    from bot.services.cache import get_redis as _gcr
    _r2 = await _gcr()
    await _r2.set(f"vk:sending:{uid}", "1", ex=120)

    try:
        # Держим «печатает» 1 минуту — обновляем каждые 5 сек
        for _ in range(12):
            try:
                await api.messages.set_activity(peer_id=uid, type="typing")
            except Exception:
                pass
            await asyncio.sleep(5)

        name   = profile.get("name", "душа моя")
        gender = profile.get("gender", "unknown")
        adj    = "хорошая" if gender == "female" else "хороший"

        offer_text = (
            f"{'Моя' if adj == 'хорошая' else 'Мой'} {adj} {name} {_emo()}\n\n"
            f"Я готова работать с вами на протяжении всего месяца и отвечать на все ваши вопросы.\n\n"
            f"Задавайте мне вопросы каждый день — я буду отвечать лично, глубоко и честно.\n\n"
            f"✨ Работа со мной — 990 ₽ / месяц"
        )

        from bot.vk_dialog.payments import create_payment_link as _vk_link
        try:
            link = _vk_link(uid, "monthly_990")
            offer_text += f"\n\n{link}"
        except Exception:
            pass

        await set_stage(uid, "waiting_payment")
        await _typing_medium(api, uid)
        await _send(api, uid, offer_text)
    finally:
        await _r2.delete(f"vk:sending:{uid}")


# ─── Статичные парирования VK ─────────────────────────────────────────────────

_VK_DEFLECT_GENERIC = [
    "Душа моя, я уже смотрю вашу ситуацию дальше — но для глубокой работы нужно открыть особое пространство.",
    "Ваш вопрос глубже чем кажется. Именно для такой работы я предлагаю быть рядом на целый месяц.",
    "Чтобы я могла работать с вами полноценно — нужна подписка. Я жду вас.",
    "За каждым вопросом стоит целая история. Именно её я готова смотреть с вами каждый день.",
    "Я вижу в вашей ситуации несколько важных линий. Для их полного разбора нужна совместная работа.",
    "Правда редко приходит с первого раза. Именно поэтому я работаю с людьми весь месяц.",
]
_VK_DEFLECT_NO_MONEY = [
    "Понимаю вас, душа моя. Когда будете готовы — я здесь. Ссылка никуда не денется.",
    "990 ₽ — это меньше одного похода в кафе, но целый месяц работы со мной каждый день.",
    "Самые важные вложения — в понимание себя и своей жизни. Я жду вас когда будете готовы.",
    "Деньги приходят и уходят, душа моя. Но момент — он не случаен. Я жду вас.",
]
_VK_DEFLECT_ONE_MORE = [
    "Маленьких вопросов не бывает — за каждым стоит целая жизнь. Оформите доступ — и я с вами.",
    "Один вопрос только открывает дверь. За ней — целый коридор. Я готова пройти его с вами весь месяц.",
    "За «ещё одним вопросом» всегда стоит «ещё один» — это и есть жизнь. Я рядом весь месяц.",
    "Всего один? Душа моя, за этим ответом придёт следующий. Именно для этого — работа на месяц.",
]
_VK_DEFLECT_LATER = [
    "Жизненные вопросы не любят ждать — ситуация может измениться, а момент уйти. Я здесь прямо сейчас.",
    "Душа моя, «потом» часто превращается в «никогда». Ссылка открыта — это займёт минуту.",
    "Сейчас — самое время. Завтра будет новая ситуация и новый вопрос. Я здесь.",
    "Лучшего момента не будет, душа моя. Тот, кто ищет ответы — находит их. Ссылка открыта.",
    "«Потом» — это слово которое откладывает ответы на важные вопросы. Я здесь прямо сейчас.",
]
_VK_DEFLECT_DISCOUNT = [
    "990 ₽ в месяц — это меньше чашки кофе в неделю. Зато каждый день я рядом с вами.",
    "Моя работа — это время и внимание для вас каждый день. Ценность не меняется.",
    "Скидок нет, душа моя — потому что я вкладываю в каждый ответ всё своё внимание.",
]
_VK_DEFLECT_DOUBT = [
    "Вы уже получили ответ и почувствовали его точность. Именно это и есть моя работа.",
    "Верить необязательно — нужно просто смотреть на результат. Первый ответ вы уже оценили.",
    "Я не угадываю — я читаю то, что написано в ваших числах. Именно поэтому ответ попал в точку.",
]
_VK_DEFLECT_SERVICE = [
    "Каждый день вы можете задавать мне вопросы — про любую сферу жизни. Я отвечаю лично и глубоко.",
    "Про всё что волнует — работу, любовь, семью, деньги. Именно для этого я рядом весь месяц.",
]

_VK_NO_MONEY_KW = ["нет денег", "нету денег", "денег нет", "не могу", "дорого", "финансы", "зарплата", "пенсия", "студент", "нищ", "бедн"]
_VK_ONE_MORE_KW = ["ещё один", "еще один", "один вопрос", "ещё раз", "ещё вопрос", "можно спросить", "разочек", "один разок", "уточнить", "последний"]
_VK_LATER_KW = ["потом", "позже", "подумаю", "не сейчас", "завтра", "посоветуюсь", "посмотрю", "может быть", "подумать", "время нужно", "после"]
_VK_DISCOUNT_KW = ["скидк", "дешевле", "снизьте", "меньше", "акци", "промокод"]
_VK_DOUBT_KW = ["не верю", "откуда знаете", "придумано", "не угадали", "неправда", "не работает", "сомневаюсь"]
_VK_SERVICE_KW = ["сколько вопросов", "как быстро", "что входит", "как отменить", "как работает", "про что можно"]

_VK_DAILY_LIMIT_RESPONSES = [
    "Душа моя, у меня сейчас накопилось много дел. Как только освобожусь — обязательно вернусь к вам 🌙",
    "Прошу прощения, душа моя — сейчас я очень занята. Как только появится время — я вернусь и дам знать ✨",
    "Простите, душа моя — дел сейчас много. Как только смогу — обязательно отвечу вам 💫",
    "Голубчик, сейчас у меня очень насыщенное время. Обязательно вернусь к вам как только освобожусь 🌟",
    "Прошу понять, душа моя — сейчас много всего навалилось. Я вернусь к вам обязательно 🌙",
    "Душа моя, сейчас у меня много важных дел. Как только появится время — я вернусь и дам знать 🌙",
    "Прошу прощения — сейчас я занята. Как только освобожусь — обязательно напишу вам 💫",
    "Голубчик, накопилось много дел. Я вернусь к вам как только смогу ✨",
    "Простите, душа моя — сейчас непростое время. Как только появится минутка — обязательно отвечу 🌟",
    "У меня сейчас много всего, душа моя. Вернусь к вам обязательно — просто дайте немного времени 🌙",
    "Прошу немного потерпеть, душа моя — дел накопилось. Как только освобожусь — я здесь 💫",
    "Душа моя, сейчас я очень занята важными делами. Обязательно вернусь и напишу вам ✨",
    "Голубчик, у меня сейчас насыщенный период. Как только смогу — сразу к вам 🌙",
    "Простите, много дел навалилось, душа моя. Я не забыла о вас — вернусь как только смогу 🌟",
    "Прошу прощения — сейчас у меня нет возможности. Как только освобожусь — обязательно напишу 💫",
    "Душа моя, дайте мне немного времени — у меня сейчас очень много дел. Вернусь обязательно 🌙",
    "Голубчик, сейчас я занята. Как только появится время — я вернусь и дам знать ✨",
    "Прошу понять, душа моя — у меня сейчас много всего. Обязательно отвечу как только смогу 💫",
    "Сейчас непростое время, душа моя — много дел. Я помню о вас и обязательно вернусь 🌟",
    "Душа моя, у меня сейчас накопилось немало забот. Как только разберусь — сразу к вам 🌙",
    "Прошу немного подождать — дел сейчас много, душа моя. Я обязательно вернусь ✨",
    "Простите, душа моя — сейчас очень много всего. Как только появится время — я здесь 💫",
    "Голубчик, у меня сейчас плотное время. Вернусь к вам как только освобожусь 🌙",
    "Душа моя, прошу немного терпения — много важных дел. Обязательно вернусь и напишу 🌟",
    "Сейчас у меня много дел, душа моя. Как только смогу — обязательно к вам ✨",
    "Простите, душа моя — накопилось много всего. Я не забываю о вас — вернусь обязательно 🌙",
    "Прошу немного подождать, душа моя — у меня сейчас много важного. Как только освобожусь — напишу 💫",
    "Душа моя, сейчас у меня очень занятое время. Вернусь к вам как только появится возможность 🌟",
    "Голубчик, дел сейчас много — прошу понять. Я обязательно вернусь к вам 🌙",
    "Простите, душа моя — сейчас совсем нет минутки. Как только освобожусь — я здесь и дам знать ✨",
]

_VK_DAILY_LIMIT = 3


_VK_WARM_CLOSING_FEMALE = [
    "Рада была помочь, душа моя 🌙 Если появятся ещё вопросы — я здесь.",
    "Пожалуйста, голубушка ✨ Я жду вас.",
    "Всегда рада, моя хорошая 🌟",
]
_VK_WARM_CLOSING_MALE = [
    "Рада была помочь, душа моя 🌙 Если появятся ещё вопросы — я здесь.",
    "Пожалуйста, голубчик ✨ Я жду вас.",
    "Всегда рада, мой хороший 🌟",
]
_VK_CLOSING_WORDS = {"спасибо", "благодарю", "благодарна", "благодарен", "пожалуйста", "ок", "окей", "хорошо", "понятно", "ясно"}


async def _stage_answered_vk(api, uid: int, text: str) -> None:
    """После первого бесплатного ответа — парируем, оффер уже запланирован."""
    t = text.lower().strip()

    # Благодарности — тёплый ответ без продажи
    if len(t) < 25 and any(w in t for w in _VK_CLOSING_WORDS):
        _profile_c = await get_profile(uid)
        _gender_c  = _profile_c.get("gender", "unknown")
        _closing   = _VK_WARM_CLOSING_FEMALE if _gender_c == "female" else _VK_WARM_CLOSING_MALE
        await _typing_short(api, uid)
        await _send(api, uid, random.choice(_closing))
        return

    # Определяем тип и дедуплицируем
    from bot.services.cache import get_redis
    r = await get_redis()
    if any(k in t for k in _VK_NO_MONEY_KW):
        dtype = "no_money"
    elif any(k in t for k in _VK_ONE_MORE_KW):
        dtype = "one_more"
    elif any(k in t for k in _VK_LATER_KW):
        dtype = "later"
    elif any(k in t for k in _VK_DISCOUNT_KW):
        dtype = "discount"
    elif any(k in t for k in _VK_DOUBT_KW):
        dtype = "doubt"
    elif any(k in t for k in _VK_SERVICE_KW):
        dtype = "service"
    else:
        dtype = "generic"

    dedup_key = f"vk:deflect_last:{uid}"
    last_dtype = await r.get(dedup_key)
    if last_dtype and (last_dtype.decode() if isinstance(last_dtype, bytes) else last_dtype) == dtype:
        dtype = "generic" if dtype != "generic" else "one_more"
    await r.set(dedup_key, dtype, ex=300)

    deflect_map = {
        "no_money": _VK_DEFLECT_NO_MONEY,
        "one_more": _VK_DEFLECT_ONE_MORE,
        "later":    _VK_DEFLECT_LATER,
        "discount": _VK_DEFLECT_DISCOUNT,
        "doubt":    _VK_DEFLECT_DOUBT,
        "service":  _VK_DEFLECT_SERVICE,
        "generic":  _VK_DEFLECT_GENERIC,
    }
    reply = random.choice(deflect_map.get(dtype, _VK_DEFLECT_GENERIC))
    await _typing_short(api, uid)
    await _send(api, uid, reply)


async def _stage_paid_monthly_vk(api, uid: int, text: str) -> None:
    """Платная ежемесячная подписка VK: 3 AI-вопроса в день."""
    from bot.services.cache import get_redis
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r     = await get_redis()
    key   = f"vk:daily_paid:{uid}:{today}"
    count = int(await r.get(key) or 0)

    if count >= _VK_DAILY_LIMIT:
        limit_notified_key = f"vk:limit_notified:{uid}:{today}"
        already_notified   = await r.get(limit_notified_key)
        if not already_notified:
            from datetime import datetime as _dt
            day_of_month = _dt.now().day
            msg = _VK_DAILY_LIMIT_RESPONSES[(day_of_month - 1) % len(_VK_DAILY_LIMIT_RESPONSES)]
            await _typing_short(api, uid)
            await _send(api, uid, msg)
            await r.set(limit_notified_key, "1", ex=86400)
        # На все последующие — молчим
        return

    await r.incr(key)
    await r.expire(key, 86400)

    profile = await get_profile(uid)
    context = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "city":       profile.get("city", ""),
        "question":   text,
    }, ensure_ascii=False)

    from bot.prompts.prompts import PERSONAL_QUESTION_PAID_PROMPT
    resp = await generate_business(
        PERSONAL_QUESTION_PAID_PROMPT,
        f"Вопрос пользователя: {text}\n\nДанные: {context}",
        complexity="medium", max_tokens=600,
    )
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)


async def _stage_free_dialog(api, uid: int, text: str) -> None:
    if _wants_to_pay(text):
        await _send_payment_offer(api, uid, uid)
        return
    if _is_closing(text):
        pivot = random.choice([
            f"Подождите {_emo()}\n\nЯ вижу в вашей ситуации кое-что важное — то, о чём мы пока не говорили. Хотите, я посмотрю это подробнее?",
            f"Прежде чем вы уйдёте {_emo()}\n\nВ том, что вы рассказали, есть момент, который требует внимания.",
        ])
        await _typing_short(api, uid)
        await _send(api, uid, pivot)
        await _typing_long(api, uid)
        await _send_payment_offer(api, uid, uid)
        return

    free_count = await get_free_count(uid)
    if free_count >= FREE_MSG_LIMIT:
        deflect = await get_deflect_message(uid)
        await _typing_deflect(api, uid)
        await _send(api, uid, deflect)
        await _send_payment_offer(api, uid, uid)
        return

    profile      = await get_profile(uid)
    history      = await get_history(uid)
    history_text = format_history(history)
    context      = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
    }, ensure_ascii=False)

    await append_history(uid, "user", text)
    resp = await generate_business(
        AISHA_FREE_PROMPT,
        f"ИСТОРИЯ ПЕРЕПИСКИ:\n{history_text}\n\n"
        f"ПОСЛЕДНЕЕ СООБЩЕНИЕ КЛИЕНТА: {text}\n\n"
        f"Данные клиента: {context}\n\n"
        f"Ответь коротко (2–3 предложения). Не повторяй вопросы из истории. "
        f"Если клиент говорит 'я уже сказал' или 'я писал' — признай это и двигайся вперёд. "
        f"Обращайся на вы.",
        complexity="simple", max_tokens=140,
    )
    await append_history(uid, "aisha", resp)
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)
    await increment_free_count(uid)


async def _stage_waiting_payment(api, uid: int, text: str) -> None:
    """После показа оффера — только статичные парирования. Никакого AI."""
    t = text.lower().strip()

    # Благодарности — тёплый ответ
    if len(t) < 25 and any(w in t for w in _VK_CLOSING_WORDS):
        _profile_c = await get_profile(uid)
        _gender_c  = _profile_c.get("gender", "unknown")
        _closing   = _VK_WARM_CLOSING_FEMALE if _gender_c == "female" else _VK_WARM_CLOSING_MALE
        await _typing_short(api, uid)
        await _send(api, uid, random.choice(_closing))
        return

    # Всё остальное — статичное парирование из базы
    await _stage_answered_vk(api, uid, text)


async def _stage_followup(api, uid: int, text: str) -> None:
    # Сброс счётчика followup-пушей при ответе
    from bot.services.cache import get_redis
    from bot.business_dialog.handlers import _is_pre_question
    r = await get_redis()
    await r.delete(f"vk:followup_push_count:{uid}")
    await r.delete(f"vk:followup_push_dedup:{uid}")

    if _is_dissatisfied(text):
        await _handle_dissatisfaction(api, uid, text)
        return

    profile   = await get_profile(uid)
    paid_tier = await get_paid_tier(uid) or "t190"
    context_base = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
    }, ensure_ascii=False)

    # ── Мета-реплика (благодарность, короткое «ок») — не тратит слот ─────────
    if _is_pre_question(text):
        quick = await generate_business(
            AISHA_FOLLOWUP_PROMPT,
            f"Клиент написал попутную реплику или анонс вопроса: «{text}»\n\n"
            f"Ответь очень коротко (1 предложение), по смыслу. "
            f"Если это анонс вопроса — пригласи задать его. "
            f"Если благодарность — тепло прими. "
            f"НЕ задавай встречных вопросов. Обращайся на вы.\n\n"
            f"Данные: {context_base}",
            complexity="simple", max_tokens=60,
        )
        await _typing_for_text(api, uid, quick)
        await _send(api, uid, quick)
        return  # слот НЕ тратится

    # ── Реальный follow-up вопрос — тратит слот ───────────────────────────────
    left    = await decrement_followup(uid)
    context = json.dumps({
        "name":           profile.get("name", ""),
        "gender":         profile.get("gender", "unknown"),
        "birth_date":     profile.get("birth_date", ""),
        "problem":        profile.get("problem", ""),
        "followups_left": left,
    }, ensure_ascii=False)

    await append_history(uid, "user", text)
    resp = await generate_business(
        AISHA_FOLLOWUP_PROMPT,
        f"Уточняющий вопрос после консультации: {text}\n\nДанные: {context}\n\nОбращайся на вы.",
        complexity="medium", max_tokens=300,
    )
    await append_history(uid, "aisha", resp)
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)

    if left == 0:
        await _typing_short(api, uid)
        await _offer_next_upsell(api, uid, uid, paid_tier)


async def _stage_accompaniment(api, uid: int, text: str) -> None:
    if _is_dissatisfied(text):
        await _handle_dissatisfaction(api, uid, text)
        return

    paid_tier      = await get_paid_tier(uid) or "t1990"
    tier           = get_tier(paid_tier)
    msg_soft_limit = tier.get("msg_soft_limit")
    msg_count      = await get_tier_msg_count(uid)

    if msg_soft_limit and msg_count >= msg_soft_limit:
        await _offer_next_upsell(api, uid, uid, paid_tier)
        return

    # Дневной лимит (t1990: 6 в день)
    daily_limit = tier.get("daily_limit")
    if daily_limit:
        from bot.services.cache import get_redis
        r       = await get_redis()
        today   = date.today().isoformat()
        day_key = f"vk:accomp_day:{uid}:{today}"
        cnt     = await r.incr(day_key)
        if cnt == 1:
            await r.expire(day_key, 86400)
        if cnt > daily_limit:
            await _typing_short(api, uid)
            await _send(api, uid, random.choice([
                "На сегодня мы поговорили достаточно, душа моя 🌙\n\nОтдыхайте — завтра утром я буду снова рядом.",
                "Сегодня на этом остановимся ✨\n\nЗавтра в 8 утра пришлю вам план на день.",
            ]))
            return

    profile      = await get_profile(uid)
    history      = await get_history(uid)
    history_text = format_history(history)
    context      = json.dumps({
        "name":       profile.get("name", ""),
        "gender":     profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "problem":    profile.get("problem", ""),
        "tier":       paid_tier,
    }, ensure_ascii=False)

    await append_history(uid, "user", text)
    resp = await generate_business(
        AISHA_ACCOMPANIMENT_PROMPT,
        f"ИСТОРИЯ ПЕРЕПИСКИ:\n{history_text}\n\nСООБЩЕНИЕ КЛИЕНТА: {text}\n\nДанные: {context}\n\nОбращайся на вы.",
        complexity="medium", max_tokens=400,
    )
    await append_history(uid, "aisha", resp)
    await increment_tier_msg_count(uid)
    await _typing_for_text(api, uid, resp)
    await _send(api, uid, resp)


async def _stage_waiting_upsell(api, uid: int, text: str) -> None:
    if _is_dissatisfied(text):
        await _handle_dissatisfaction(api, uid, text)
        return
    profile       = await get_profile(uid)
    next_tier_key = profile.get("next_tier", "t490")
    timing        = _tier_timing_hint(next_tier_key)
    context       = json.dumps({"name": profile.get("name", ""), "problem": profile.get("problem", "")}, ensure_ascii=False)
    reply = await generate_business(
        AISHA_FREE_PROMPT,
        f"Клиент задаёт вопрос: «{text}»\n\n"
        f"Ответь КОРОТКО (1–2 предложения) по смыслу. "
        f"Не упоминай слово 'оплата'. Обращайся на вы. "
        f"НЕ задавай вопросов в конце.\n\n"
        f"ВАЖНО: если спрашивают о сроках — ответь точно: {timing}. "
        f"ВАЖНО: если о ссылке — ссылка работает в любой момент без ограничений.\n\n"
        f"Данные: {context}",
        complexity="simple", max_tokens=60,
    )
    await _typing_for_text(api, uid, reply)
    await _send(api, uid, reply)


async def _stage_t990_waiting_question(api, uid: int, text: str) -> None:
    if not text or len(text) < 4:
        await _send(api, uid, "Напишите ваш вопрос — я жду 🔮")
        return
    await store_field(uid, "t990_question", text)
    from bot.services.cache import get_redis
    r = await get_redis()
    await r.set(f"vk:t990_start:{uid}", str(time.time()), ex=86400)
    await set_stage(uid, "t990_preparing")
    await _typing_short(api, uid)
    await _send(api, uid, random.choice([
        "Принято, душа моя 🔮\n\nЗапаситесь терпением — мне нужно подготовиться, и я сразу дам вам ответ.",
        "Получила ваш вопрос 🌙\n\nМне нужно время чтобы обратиться к картам. Запаситесь терпением — как только буду готова, сразу напишу.",
    ]))
    # Запускаем фоновую доставку
    task_key = f"vk:t990_task:{uid}"
    already  = not await r.set(task_key, "1", nx=True, ex=3600)
    if not already:
        asyncio.create_task(_deliver_tarot_reading_vk(api, uid))


async def _stage_t990_preparing(api, uid: int, text: str) -> None:
    from bot.services.cache import get_redis
    r = await get_redis()
    if not await r.get(f"vk:t990_delivered:{uid}"):
        start_raw = await r.get(f"vk:t990_start:{uid}")
        if start_raw and (time.time() - float(start_raw)) >= _T990_WAIT_SECONDS:
            task_key = f"vk:t990_task:{uid}"
            if await r.set(task_key, "1", nx=True, ex=3600):
                asyncio.create_task(_deliver_tarot_reading_vk(api, uid))
            return
    profile = await get_profile(uid)
    name    = profile.get("name", "")
    reply   = await generate_business(
        AISHA_FREE_PROMPT,
        f"Ты сейчас обращаешься к картам для клиента {name}. Клиент написал: «{text}»\n\n"
        f"Ответь очень коротко (1–2 предложения) — дай понять что ты в процессе расклада. Обращайся на вы.",
        complexity="simple", max_tokens=50,
    )
    await _typing_short(api, uid)
    await _send(api, uid, reply)


async def _deliver_tarot_reading_vk(api, uid: int) -> None:
    """Фоновая задача — 8 минут, затем карта Таро + интерпретация."""
    from bot.services.cache import get_redis

    await asyncio.sleep(_T990_WAIT_SECONDS)

    r      = await get_redis()
    already = not await r.set(f"vk:t990_delivered:{uid}", "1", nx=True, ex=86400)
    if already:
        return

    stage = await get_stage(uid)
    if stage != "t990_preparing":
        return

    profile  = await get_profile(uid)
    question = profile.get("t990_question") or profile.get("problem", "")
    name     = profile.get("name", "")

    card_file, card_name, card_display = random.choice(_MAJOR_ARCANA)
    card_path = _TAROT_ASSETS / f"{card_file}.png"

    # Отправка фото карты через VK
    try:
        from vkbottle import PhotoMessageUploader
        uploader = PhotoMessageUploader(api)
        photo    = await uploader.upload(str(card_path))
        await api.messages.send(
            peer_id=uid,
            attachment=photo,
            message="",
            random_id=random.randint(1, 2**31),
        )
    except Exception as e:
        logger.warning("VK t990 photo send failed for %s: %s", uid, e)

    await _typing_short(api, uid)
    await _send(api, uid, f"Карта открылась — {card_display} 🔮\n\nСейчас расскажу, что она говорит о вашем вопросе…")

    context = json.dumps({
        "name":      name,
        "gender":    profile.get("gender", "unknown"),
        "birth_date": profile.get("birth_date", ""),
        "question":  question,
        "card":      card_display,
        "card_name": card_name,
    }, ensure_ascii=False)

    interpretation = await generate_business(
        AISHA_TAROT_BUSINESS_PROMPT,
        f"Данные клиента: {context}",
        complexity="complex", max_tokens=900,
    )
    await _typing_for_text(api, uid, interpretation)
    await _send(api, uid, interpretation)

    followup_limit = 5
    await _typing_short(api, uid)
    await _send(api, uid, followup_invite(followup_limit))
    await set_stage(uid, "followup")
    await set_followup_left(uid, followup_limit)
    if not await get_paid_tier(uid):
        await set_paid_tier(uid, "t990")


async def _stage_completed(api, uid: int) -> None:
    msgs = [
        f"Если почувствуете, что ситуация снова тревожит — можете написать мне {_emo()}",
        f"Если захотите посмотреть глубже — возвращайтесь, душа моя {_emo()}",
        f"Я здесь {_emo()}",
    ]
    await _typing_short(api, uid)
    await _send(api, uid, random.choice(msgs))


async def _handle_dissatisfaction(api, uid: int, text: str) -> None:
    profile = await get_profile(uid)
    context = json.dumps({
        "name":    profile.get("name", ""),
        "gender":  profile.get("gender", "unknown"),
        "problem": profile.get("problem", ""),
    }, ensure_ascii=False)
    reply = await generate_business(
        AISHA_FREE_PROMPT,
        f"Клиент выражает недовольство: «{text}»\n\n"
        f"Признай её/его чувства искренне. Не защищайся. "
        f"Предложи задать конкретный вопрос прямо сейчас. "
        f"2–4 предложения. Обращайся на вы. Без упоминания денег.\n\nДанные: {context}",
        complexity="simple", max_tokens=120,
    )
    await _typing_short(api, uid)
    await _send(api, uid, reply)
