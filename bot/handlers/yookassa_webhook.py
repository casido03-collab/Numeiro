"""Webhook от ЮКассы — приём уведомлений об успешных платежах."""
import json
import logging
from datetime import datetime, timedelta, timezone

from aiohttp import web
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Устанавливаются при старте бота из main.py
_bot = None
_session_maker = None


def setup_webhook(bot, session_maker):
    global _bot, _session_maker
    _bot = bot
    _session_maker = session_maker


async def handle_yookassa_webhook(request: web.Request) -> web.Response:
    """Обработчик POST /yookassa/webhook — единая точка входа для всех платежей ЮКассы.

    Маршрутизация по metadata.platform:
      - platform == "vk"  → VK-диалог (бабушка Аиша в ВКонтакте)
      - иначе             → Telegram-подписки и разовые покупки
    """
    try:
        body = await request.text()
        data = json.loads(body)
        logger.info("YooKassa webhook received: event=%s", data.get("event"))

        event = data.get("event")
        if event != "payment.succeeded":
            return web.Response(status=200)

        payment_obj = data.get("object", {})
        if payment_obj.get("status") != "succeeded":
            return web.Response(status=200)

        metadata = payment_obj.get("metadata", {})

        # ── VK-платёж ─────────────────────────────────────────────────────────
        if metadata.get("platform") == "vk":
            from bot.vk_dialog.payments import handle_vk_payment_webhook
            return await handle_vk_payment_webhook(request, _parsed=(data, payment_obj, metadata))

        # ── TG бизнес-диалог (бабушка Аиша) ───────────────────────────────────
        if metadata.get("platform") == "tg_business":
            telegram_id = int(metadata.get("telegram_id", 0))
            tier_key    = metadata.get("tier_key", "t190")
            payment_id  = payment_obj.get("id", "")
            amount      = int(float(payment_obj.get("amount", {}).get("value", 0)))
            if telegram_id:
                from bot.services.cache import get_redis
                _r = await get_redis()
                already = not await _r.set(f"tg_biz_paid:{payment_id}", "1", nx=True, ex=86400)
                if not already:
                    if tier_key == "monthly_990":
                        # Новый тир — ежемесячная подписка
                        from bot.business_dialog.session_manager import set_biz_stage, get_biz_conn
                        await set_biz_stage(telegram_id, "paid_monthly")
                        # Сохраняем дату окончания подписки
                        import time
                        await _r.set(f"biz:paid_until:{telegram_id}", str(int(time.time()) + 86400 * 30), ex=86400 * 31)
                        # Отправляем подтверждение
                        biz_conn_id = await get_biz_conn(telegram_id)
                        if _bot:
                            confirm = "Оплата прошла, душа моя 🌙\n\nТеперь я с вами весь месяц. Задавайте вопросы — я здесь."
                            send_kw: dict = {"chat_id": telegram_id, "text": confirm}
                            if biz_conn_id:
                                send_kw["business_connection_id"] = biz_conn_id
                            try:
                                await _bot.send_message(**send_kw)
                            except Exception as e:
                                logger.warning("monthly_990 confirm failed: %s", e)
                        logger.info("TG monthly_990 activated: tid=%s", telegram_id)
                    else:
                        from bot.business_dialog.tribute_flow import _process_payment, _session_maker as _trib_sm
                        if _trib_sm:
                            async with _trib_sm() as session:
                                await _process_payment(session, telegram_id, payment_id, amount, tier_key)
                            logger.info("TG business payment processed: tid=%s tier=%s", telegram_id, tier_key)
            return web.Response(status=200)

        # ── Telegram-платёж ───────────────────────────────────────────────────
        payment_id       = payment_obj.get("id")
        user_telegram_id = metadata.get("user_id")
        product_type     = metadata.get("product_type")
        product_key      = metadata.get("product_key")
        amount           = float(payment_obj.get("amount", {}).get("value", 0))

        if not all([user_telegram_id, product_type, product_key]):
            logger.error("Webhook: missing metadata in payment %s — %s", payment_id, metadata)
            return web.Response(status=200)

        # Защита от двойной обработки через Redis
        from bot.services.cache import get_redis
        redis = await get_redis()
        already_processed = await redis.set(
            f"yk_paid:{payment_id}", "1", nx=True, ex=3600 * 24
        )
        if not already_processed:
            logger.warning("Webhook: payment %s already processed, skip", payment_id)
            return web.Response(status=200)

        await _process_payment(
            telegram_id=int(user_telegram_id),
            product_type=product_type,
            product_key=product_key,
            amount=amount,
            payment_id=payment_id,
        )

    except Exception:
        logger.exception("YooKassa webhook error")

    return web.Response(status=200)


async def _process_payment(
    telegram_id: int,
    product_type: str,
    product_key: str,
    amount: float,
    payment_id: str,
):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.models.user import User, Payment
    from bot.handlers.payments import (
        PLAN_DISPLAY,
        PRODUCT_DISPLAY,
        _activate_subscription,
        _activate_one_time_product,
        _process_referral_reward,
        _product_callback,
    )

    async with _session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.error("Webhook: user telegram_id=%s not found", telegram_id)
            return

        # Сохраняем платёж в БД
        session.add(Payment(
            user_id=user.id,
            telegram_payment_charge_id=payment_id,
            amount=int(amount * 100),  # копейки
            currency="RUB",
            product_type=f"{product_type}:{product_key}",
            status="completed",
        ))

        if product_type == "plan":
            await _activate_subscription(session, user, product_key)
            info = PLAN_DISPLAY.get(product_key, {})
            text = (
                f"✅ *Подписка {info.get('label', product_key)} активирована!*\n\n"
                f"Доступ открыт на *{info.get('period', '30 дней')}*. 🌟"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔮 Перейти к разборам", callback_data="menu:main")]
            ])
        else:
            await _activate_one_time_product(session, user, product_key)
            info = PRODUCT_DISPLAY.get(product_key, {})
            text = (
                f"✅ *{info.get('label', product_key)} куплен!*\n\n"
                f"Функция доступна для использования. 🌟"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔮 Использовать сейчас",
                    callback_data=_product_callback(product_key),
                )]
            ])

        await _process_referral_reward(session, user, _bot)
        await session.commit()

    try:
        await _bot.send_message(
            telegram_id, text, parse_mode="Markdown", reply_markup=keyboard
        )
    except Exception:
        logger.exception("Failed to notify user %s after payment", telegram_id)
