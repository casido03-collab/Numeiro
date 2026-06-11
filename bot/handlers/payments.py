"""Платежи — выбор метода (карта / Stars) + Telegram Payments API."""
import logging
import re
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import User, Payment, Subscription, PlanEnum, SubscriptionStatusEnum
from bot.keyboards.main import (
    plans_keyboard, one_time_products_keyboard, back_to_main,
)
from config import PLANS, ONE_TIME_PRODUCTS, settings

router = Router()
logger = logging.getLogger(__name__)


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))

PLAN_DISPLAY = {
    "lite":    {"label": "Lite",    "price": 299,  "period": "7 дней"},
    "premium": {"label": "Premium", "price": 999,  "period": "месяц"},
    "pro":     {"label": "Pro",     "price": 1499, "period": "месяц"},
}

PRODUCT_DISPLAY = {
    "full_matrix":       {"label": "Полная матрица судьбы",    "price": 299},
    "compatibility":     {"label": "Совместимость пары",       "price": 199},
    "weekly_report":     {"label": "Расклад на неделю",        "price": 199},
    "personal_question": {"label": "Личный вопрос Тарологу",   "price": 99},
    "date_selection":    {"label": "Подбор благоприятных дат", "price": 199},
}

PRODUCT_DESCRIPTIONS = {
    "full_matrix":       "Полный разбор всех арканов матрицы судьбы",
    "compatibility":     "Один полный анализ совместимости пары",
    "weekly_report":     "Детальный расклад на ближайшие 7 дней",
    "personal_question": "Один личный вопрос судьбе",
    "date_selection":    "Подбор 5 благоприятных дат для события",
}


# ─── Шаг 1: нажатие кнопки тарифа / продукта → Stars-инвойс сразу ────────────

async def _send_stars_invoice(callback: CallbackQuery, product_type: str, product_key: str):
    """Отправляет Telegram Stars invoice напрямую, без промежуточного экрана."""
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Товар не найден")
        return
    label = info["label"]
    stars = info["price"]
    desc = PRODUCT_DESCRIPTIONS.get(product_key, label)
    payload = f"{product_type}:{product_key}"
    await callback.message.answer_invoice(
        title=label,
        description=desc,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:plan:"))
async def buy_plan_choose_method(callback: CallbackQuery, lang: str = "ru"):
    plan_key = callback.data.split(":")[-1]
    await _send_stars_invoice(callback, "plan", plan_key)


@router.callback_query(F.data.startswith("buy:product:"))
async def buy_product_choose_method(callback: CallbackQuery, lang: str = "ru"):
    product_key = callback.data.split(":")[-1]
    await _send_stars_invoice(callback, "product", product_key)


# ─── Шаг 2а: pay:card → заглушка (Юкасса отключена) ─────────────────────────

@router.callback_query(F.data.startswith("pay:card:"))
async def card_pay_disabled(callback: CallbackQuery):
    parts = callback.data.split(":")
    product_type = parts[2] if len(parts) > 2 else ""
    product_key  = parts[3] if len(parts) > 3 else ""
    await callback.answer("⭐ Доступна только оплата Telegram Stars", show_alert=True)
    # Перенаправляем сразу на Stars-инвойс
    await _send_stars_invoice(callback, product_type, product_key)


# ─── Шаг 2б: выбраны Stars → счёт ────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:stars:"))
async def stars_pay_invoice(callback: CallbackQuery, user: User):
    parts = callback.data.split(":")  # ['pay', 'stars', type, key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Товар не найден")
        return

    label = info["label"]
    stars = info["price"]  # 1 ₽ = 1 Star
    desc = PRODUCT_DESCRIPTIONS.get(product_key, label)
    payload = f"{product_type}:{product_key}"

    await callback.message.answer_invoice(
        title=label,
        description=desc,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )
    await callback.answer()


# ─── Навигация: pay:method → редирект на Stars-инвойс ────────────────────────

@router.callback_query(F.data.startswith("pay:method:"))
async def back_to_pay_method(callback: CallbackQuery, lang: str = "ru"):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    await _send_stars_invoice(callback, product_type, product_key)


# ─── Навигация: разовые покупки ───────────────────────────────────────────────

@router.callback_query(F.data == "buy:oneoff")
async def buy_oneoff(callback: CallbackQuery):
    await callback.message.edit_text(
        "💎 *Разовые покупки*\n\nВыбери нужный продукт:",
        reply_markup=one_time_products_keyboard(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Telegram pre-checkout ────────────────────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# ─── Успешная оплата ──────────────────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment(message: Message, user: User, session: AsyncSession):
    payment = message.successful_payment
    payload = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id

    p = Payment(
        user_id=user.id,
        telegram_payment_charge_id=charge_id,
        amount=payment.total_amount,
        currency=payment.currency,
        product_type=payload,
        status="completed",
    )
    session.add(p)

    if payload.startswith("plan:"):
        plan_key = payload.split(":")[-1]
        await _activate_subscription(session, user, plan_key)
        info = PLAN_DISPLAY.get(plan_key, {})
        period_text = f"{info.get('days', 30)} дней" if plan_key == "lite" else "месяц"
        await message.answer(
            f"✅ *Подписка {info.get('label', plan_key)} активирована!*\n\n"
            f"Доступ открыт на *{info.get('period', '30 дней')}*. 🌟",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔮 Перейти к разборам", callback_data="menu:main")]
            ]),
        )

    elif payload.startswith("product:"):
        product_key = payload.split(":")[-1]
        await _activate_one_time_product(session, user, product_key)
        info = PRODUCT_DISPLAY.get(product_key, {})
        await message.answer(
            f"✅ *{info.get('label', product_key)} куплен!*\n\n"
            f"Функция доступна для использования. 🌟",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔮 Использовать сейчас", callback_data=_product_callback(product_key))]
            ]),
        )

    elif payload == "biz_monthly_990":
        # Подписка бизнес-чата через Stars — активируем paid_monthly
        from bot.business_dialog.session_manager import set_biz_stage, get_biz_conn
        from bot.services.cache import get_redis
        import time as _time
        r = await get_redis()
        await set_biz_stage(user.telegram_id, "paid_monthly")
        await r.set(f"biz:paid_until:{user.telegram_id}", str(int(_time.time()) + 86400 * 30), ex=86400 * 31)
        biz_conn_id = await get_biz_conn(user.telegram_id)
        confirm = "Оплата прошла, душа моя 🌙\n\nТеперь я с вами весь месяц. Задавайте вопросы — я здесь."
        if biz_conn_id:
            try:
                await message.bot.send_message(
                    chat_id=user.telegram_id,
                    text=confirm,
                    business_connection_id=biz_conn_id,
                )
            except Exception:
                pass
        await message.answer(
            "✅ *Подписка активирована!*\n\nВернитесь в чат с Бабушкой Aisha — она уже ждёт вас. 🌙",
            parse_mode="Markdown",
        )

    await _process_referral_reward(session, user, message.bot)
    await session.commit()


# ─── Вспомогательные ──────────────────────────────────────────────────────────

async def _activate_subscription(session: AsyncSession, user: User, plan_key: str):
    plan = PLANS.get(plan_key)
    if not plan:
        return
    days = plan.get("days", 30)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    # Дата активации = сегодня = ключ периода для этой подписки
    period_key = now.strftime("%Y-%m-%d")

    result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if sub:
        sub.plan = PlanEnum(plan_key)
        sub.status = SubscriptionStatusEnum.active
        sub.expires_at = expires
    else:
        session.add(Subscription(
            user_id=user.id,
            plan=PlanEnum(plan_key),
            status=SubscriptionStatusEnum.active,
            expires_at=expires,
        ))
        await session.flush()

    # Сброс лимитов на новый период подписки
    # Используем period_key напрямую (не через get_or_create_usage) — избегаем гонки с сессией
    from bot.models.user import UsageLimits
    usage_res = await session.execute(
        select(UsageLimits).where(
            UsageLimits.user_id == user.id,
            UsageLimits.period_start == period_key,
        )
    )
    usage = usage_res.scalar_one_or_none()
    if not usage:
        usage = UsageLimits(user_id=user.id, period_start=period_key)
        session.add(usage)
        await session.flush()

    # Сбрасываем все периодные лимиты (daily_forecasts не трогаем — он сбрасывается сам каждый день)
    for field in ("ai_messages", "personal_questions", "weekly_reports",
                  "compatibility", "mini_readings", "date_selections"):
        setattr(usage, field, 0)


async def _activate_one_time_product(session: AsyncSession, user: User, product_key: str):
    from bot.services.cache import get_redis
    r = await get_redis()
    await r.incr(f"oneoff:{product_key}:{user.id}")
    await r.expire(f"oneoff:{product_key}:{user.id}", 3600 * 24 * 30)


async def _process_referral_reward(session: AsyncSession, user: User, bot):
    from bot.models.user import Referral, User as UserModel
    if not user.invited_by:
        return
    result = await session.execute(
        select(Referral).where(
            Referral.invited_telegram_id == user.telegram_id,
            Referral.reward_given == False,   # noqa: E712
        )
    )
    ref = result.scalar_one_or_none()
    if not ref:
        return

    inviter_res = await session.execute(select(UserModel).where(UserModel.telegram_id == user.invited_by))
    inviter = inviter_res.scalar_one_or_none()
    if not inviter:
        return

    sub_res = await session.execute(select(Subscription).where(Subscription.user_id == inviter.id))
    inviter_sub = sub_res.scalar_one_or_none()

    ref.reward_given = True
    ref.purchase_status = True

    if inviter_sub and inviter_sub.expires_at:
        # Подписка есть — просто добавить день (работает и для истёкших: сдвигаем expires_at)
        inviter_sub.expires_at += timedelta(days=1)
        if inviter_sub.status != SubscriptionStatusEnum.active:
            # Если истекла, всё равно продлеваем — бонус сохранится
            pass
    else:
        # Нет подписки вообще — создать запись с нулевым тарифом и expires_at = now + 1 день
        # Это "копилка" бонусных дней до первой покупки
        from datetime import datetime as _dt
        bonus_sub = Subscription(
            user_id=inviter.id,
            plan=PlanEnum.free,
            status=SubscriptionStatusEnum.expired,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        session.add(bonus_sub)

    try:
        await bot.send_message(
            inviter.telegram_id,
            "🎁 *Твой реферал совершил покупку!*\n\n✨ +1 день добавлен к твоей подписке.",
            parse_mode="Markdown",
        )
    except Exception:
        pass


def _product_callback(product_key: str) -> str:
    return {
        "full_matrix":       "matrix:start",
        "compatibility":     "compat:start",
        "weekly_report":     "weekly:start",
        "personal_question": "menu:question",
        "date_selection":    "menu:dates",
    }.get(product_key, "menu:main")
