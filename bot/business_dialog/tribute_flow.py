"""Tribute payment integration — ссылка на оплату + обработка webhook."""
import hashlib
import hmac
import json
import logging

from aiohttp import web
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Инициализируются из router.py при старте
_bot: Bot | None = None
_session_maker = None

TRIBUTE_PRICE = 190  # ₽ — базовая цена первого тира (для обратной совместимости)


def setup_tribute(bot: Bot, session_maker) -> None:
    global _bot, _session_maker
    _bot = bot
    _session_maker = session_maker


def _tribute_link() -> str:
    from config import settings
    return getattr(settings, "tribute_link", "")


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def payment_keyboard(tier_key: str = "t190") -> InlineKeyboardMarkup:
    """Кнопка оплаты для конкретного тира."""
    from bot.business_dialog.upsell import tier_link, get_tier
    link  = tier_link(tier_key)
    price = get_tier(tier_key).get("price", TRIBUTE_PRICE)
    rows  = []
    if link:
        rows.append([InlineKeyboardButton(text=f"💎 Оплатить — {price} ₽", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def return_payment_keyboard(tier_key: str = "t190") -> InlineKeyboardMarkup:
    """Кнопка возврата к оплате для конкретного тира."""
    from bot.business_dialog.upsell import tier_link, get_tier
    link  = tier_link(tier_key)
    price = get_tier(tier_key).get("price", TRIBUTE_PRICE)
    rows  = []
    if link:
        rows.append([InlineKeyboardButton(text=f"💎 Вернуться к оплате — {price} ₽", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Webhook handler ──────────────────────────────────────────────────────────

def _verify_tribute_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Проверить HMAC-SHA256 подпись от Tribute."""
    if not secret:
        return True  # ключ не настроен — пропускаем (dev-режим)
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_tribute_webhook(request: web.Request) -> web.Response:
    """POST /webhooks/tribute — уведомление об оплате от Tribute."""
    raw_body = await request.read()

    # Проверка подписи
    from config import settings
    sig_header = request.headers.get("trbt-signature", "")
    if settings.tribute_api_key and not _verify_tribute_signature(
        raw_body, sig_header, settings.tribute_api_key
    ):
        logger.warning("Tribute webhook: invalid signature")
        return web.Response(status=401, text="invalid signature")

    try:
        body = json.loads(raw_body)
    except Exception:
        logger.warning("Tribute webhook: bad JSON")
        return web.Response(status=400, text="bad json")

    # Tribute оборачивает данные в "payload"
    payload     = body.get("payload", body)  # fallback на корень если нет обёртки
    telegram_id = payload.get("telegram_user_id") or payload.get("telegram_id")
    payment_id  = str(payload.get("purchase_id") or payload.get("payment_id") or body.get("purchase_id", ""))
    status      = payload.get("status", "paid")  # Tribute шлёт webhook только при успехе
    amount      = int(payload.get("amount", 0))
    product_id  = str(payload.get("product_id", ""))

    logger.info(
        "Tribute webhook: tid=%s payment=%s status=%s amount=%s",
        telegram_id, payment_id, status, amount,
    )

    if not telegram_id:
        return web.Response(status=200, text="ok")

    # Дедупликация
    from bot.services.cache import get_redis
    r = await get_redis()
    already = not await r.set(f"trib_paid:{payment_id}", "1", nx=True, ex=86400)
    if already:
        logger.info("Tribute: payment %s already processed", payment_id)
        return web.Response(status=200, text="ok")

    if _bot and _session_maker:
        async with _session_maker() as session:
            await _process_payment(session, int(telegram_id), payment_id, amount, product_id)

    return web.Response(status=200, text="ok")


async def _process_payment(
    session, telegram_id: int, payment_id: str, amount: int, product_id: str
) -> None:
    """Активировать консультацию после подтверждённой оплаты (любой тир)."""
    from sqlalchemy import select
    from bot.business_dialog.models import BusinessSession, BusinessPayment
    from bot.business_dialog.session_manager import (
        get_biz_conn, set_biz_stage, get_profile, set_followup_left,
        set_paid_tier, reset_tier_msg_count,
    )
    from bot.business_dialog.typing_simulation import typing_long
    from bot.business_dialog.services import generate_business
    from bot.business_dialog.prompts import (
        AISHA_PAID_PROMPT, AISHA_CAUSE_PROMPT,
        AISHA_FORECAST_PROMPT, AISHA_ACCOMPANIMENT_PROMPT,
    )
    from bot.business_dialog.upsell import get_tier_by_amount, get_tier, is_accompaniment

    # Определяем тир по сумме оплаты
    tier_key = get_tier_by_amount(amount)
    tier     = get_tier(tier_key)
    followup_limit = tier.get("followup_limit") or 2

    # Запись платежа
    session.add(BusinessPayment(
        telegram_id=telegram_id,
        payment_id=payment_id,
        amount=amount,
        status="paid",
        product_id=product_id,
    ))

    # Обновление сессии в БД
    res = await session.execute(
        select(BusinessSession).where(BusinessSession.telegram_id == telegram_id)
    )
    biz_sess = res.scalar_one_or_none()
    if biz_sess:
        biz_sess.status = "paid"
        biz_sess.payment_id = payment_id
        biz_sess.followup_questions_left = followup_limit
    await session.commit()

    # Redis: сохранить тир, сбросить счётчики
    await set_paid_tier(telegram_id, tier_key)
    await reset_tier_msg_count(telegram_id)
    await set_biz_stage(telegram_id, "paid")
    await set_followup_left(telegram_id, followup_limit)

    biz_conn_id = await get_biz_conn(telegram_id)

    if not _bot:
        return

    async def _send(text: str, **kwargs):
        kw: dict = {"chat_id": telegram_id, "text": text, "parse_mode": None}
        if biz_conn_id:
            kw["business_connection_id"] = biz_conn_id
        kw.update(kwargs)
        try:
            await _bot.send_message(**kw)
        except Exception as e:
            logger.warning("Tribute: send failed for %s: %s", telegram_id, e)

    # Подтверждение оплаты
    confirm_msgs = {
        "t190":  "Оплата прошла, душа моя 🌙\n\nСейчас я спокойно посмотрю вашу ситуацию…",
        "t490":  "Получила, душа моя ✨\n\nСейчас буду смотреть причину — глубоко и внимательно…",
        "t990":  "Оплата прошла 💫\n\nПосмотрю ближайший период вашей ситуации — уже начинаю…",
        "t1990": "Я рядом, душа моя 🌟\n\nТеперь я буду наблюдать за вашей ситуацией — спокойно и внимательно…",
        "t4990": "Оплата прошла 🔮\n\nНачинаю наблюдение — буду рядом…",
        "t9900": "Получила, душа моя 💎\n\nЭто особенный просмотр — приступаю…",
    }
    await _send(confirm_msgs.get(tier_key, "Оплата прошла 🌙\n\nСейчас посмотрю вашу ситуацию…"))

    # Имитация работы
    await typing_long(_bot, telegram_id, biz_conn_id)

    # Выбор промпта по тиру
    _TIER_PROMPTS = {
        "t190":  (AISHA_PAID_PROMPT,        "complex", 900),
        "t490":  (AISHA_CAUSE_PROMPT,       "complex", 900),
        "t990":  (AISHA_FORECAST_PROMPT,    "complex", 1000),
        "t1990": (AISHA_ACCOMPANIMENT_PROMPT, "medium", 500),
        "t4990": (AISHA_ACCOMPANIMENT_PROMPT, "medium", 500),
        "t9900": (AISHA_ACCOMPANIMENT_PROMPT, "complex", 600),
    }
    prompt, complexity, max_tokens = _TIER_PROMPTS.get(tier_key, (AISHA_PAID_PROMPT, "complex", 900))

    profile = await get_profile(telegram_id)
    context = json.dumps(profile, ensure_ascii=False)

    consultation = await generate_business(
        prompt,
        f"Данные клиента: {context}",
        complexity=complexity,
        max_tokens=max_tokens,
    )

    # Сохранить текст консультации
    if biz_sess:
        biz_sess.consultation_text = consultation
        await session.commit()

    # Отправить разбор
    await _send(consultation)

    # Сообщение о возможностях после разбора
    await typing_long(_bot, telegram_id, biz_conn_id)

    if is_accompaniment(tier_key):
        # Сопровождение — без фиксированного числа вопросов
        await _send(
            "Я рядом, душа моя 🌙\n\nПишите когда почувствуете что-то важное — я буду отвечать."
        )
        await set_biz_stage(telegram_id, "accompaniment")
    else:
        # Разовый разбор — есть лимит follow-up
        await _send(
            f"После просмотра вы можете задать ещё {followup_limit} уточняющих вопроса 🌙\n\nНапишите — я слушаю."
        )
        await set_biz_stage(telegram_id, "followup")
