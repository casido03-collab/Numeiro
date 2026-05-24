"""Tribute payment integration — ссылка на оплату + обработка webhook."""
import json
import logging

from aiohttp import web
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

# Инициализируются из router.py при старте
_bot: Bot | None = None
_session_maker = None

TRIBUTE_PRICE = 190  # ₽


def setup_tribute(bot: Bot, session_maker) -> None:
    global _bot, _session_maker
    _bot = bot
    _session_maker = session_maker


def _tribute_link() -> str:
    from config import settings
    return getattr(settings, "tribute_link", "")


# ─── Клавиатуры ───────────────────────────────────────────────────────────────

def payment_keyboard() -> InlineKeyboardMarkup:
    link = _tribute_link()
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text=f"💎 Оплатить разбор — {TRIBUTE_PRICE} ₽", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def return_payment_keyboard() -> InlineKeyboardMarkup:
    link = _tribute_link()
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="💎 Вернуться к оплате", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Webhook handler ──────────────────────────────────────────────────────────

async def handle_tribute_webhook(request: web.Request) -> web.Response:
    """POST /webhooks/tribute — уведомление об оплате от Tribute."""
    try:
        body = await request.json()
    except Exception:
        logger.warning("Tribute webhook: bad JSON")
        return web.Response(status=400, text="bad json")

    telegram_id = body.get("telegram_id")
    payment_id  = body.get("payment_id", "")
    status      = body.get("status", "")
    amount      = int(body.get("amount", 0))
    product_id  = body.get("product_id", "")

    logger.info(
        "Tribute webhook: tid=%s payment=%s status=%s amount=%s",
        telegram_id, payment_id, status, amount,
    )

    if status != "paid" or not telegram_id:
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
    """Активировать консультацию после подтверждённой оплаты."""
    from sqlalchemy import select
    from bot.business_dialog.models import BusinessSession, BusinessPayment, BusinessProfile
    from bot.business_dialog.session_manager import (
        get_biz_conn, set_biz_stage, get_profile, set_followup_left
    )
    from bot.business_dialog.typing_simulation import typing_long
    from bot.business_dialog.services import generate_business
    from bot.business_dialog.prompts import AISHA_PAID_PROMPT

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
        biz_sess.followup_questions_left = 2
    await session.commit()

    # Redis: обновить stage и followup
    await set_biz_stage(telegram_id, "paid")
    await set_followup_left(telegram_id, 2)

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
    await _send("Оплата прошла, душа моя 🌙\n\nСейчас я спокойно посмотрю твою ситуацию…")

    # Имитация работы (5–8 сек)
    await typing_long(_bot, telegram_id, biz_conn_id)

    # Генерация полного разбора
    profile = await get_profile(telegram_id)
    context = json.dumps(profile, ensure_ascii=False)

    consultation = await generate_business(
        AISHA_PAID_PROMPT,
        f"Данные клиента: {context}",
        complexity="complex",
        max_tokens=900,
    )

    # Сохранить текст консультации
    if biz_sess:
        biz_sess.consultation_text = consultation
        await session.commit()

    # Отправить разбор
    await _send(consultation)

    # Сообщение о follow-up
    await typing_long(_bot, telegram_id, biz_conn_id)
    await _send(
        "После просмотра ты можешь задать ещё 2 уточняющих вопроса 🌙\n\nПросто напиши — я слушаю."
    )

    # Обновить stage
    await set_biz_stage(telegram_id, "followup")
