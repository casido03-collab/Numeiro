"""Платежи — выбор метода (карта / Stars) + Telegram Payments API."""
import logging
import re
from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.models.user import User, Payment, Subscription, PlanEnum, SubscriptionStatusEnum
from bot.keyboards.main import (
    payment_method_keyboard, card_methods_keyboard,
    plans_keyboard, one_time_products_keyboard, back_to_main,
)
from config import PLANS, ONE_TIME_PRODUCTS, settings

router = Router()
logger = logging.getLogger(__name__)


class PaymentFSM(StatesGroup):
    waiting_email = State()


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


# ─── Шаг 1: нажатие кнопки тарифа / продукта → выбор метода ──────────────────

@router.callback_query(F.data.startswith("buy:plan:"))
async def buy_plan_choose_method(callback: CallbackQuery):
    plan_key = callback.data.split(":")[-1]
    info = PLAN_DISPLAY.get(plan_key)
    if not info:
        await callback.answer("❌ Тариф не найден")
        return

    text = (
        f"🛒 *Тариф {info['label']}* — {info['price']} ₽ / {info['period']}\n\n"
        f"Выбери способ оплаты:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_keyboard(
            product_type="plan",
            product_key=plan_key,
            stars=info["price"],
            back="menu:plans",
        ),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:product:"))
async def buy_product_choose_method(callback: CallbackQuery):
    product_key = callback.data.split(":")[-1]
    info = PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Продукт не найден")
        return

    text = (
        f"🛒 *{info['label']}* — {info['price']} ₽\n\n"
        f"Выбери способ оплаты:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=payment_method_keyboard(
            product_type="product",
            product_key=product_key,
            stars=info["price"],
            back="buy:oneoff",
        ),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Шаг 2а: оплата через ЮКассу (карта / СБП) ───────────────────────────────

@router.callback_query(F.data.startswith("pay:yookassa:"))
async def yookassa_pay(callback: CallbackQuery, user: User, state: FSMContext):
    # pay:yookassa:plan:lite  или  pay:yookassa:product:full_matrix
    parts = callback.data.split(":")  # ['pay', 'yookassa', type, key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Товар не найден")
        return

    if not settings.yookassa_secret_key:
        await callback.answer("⚠️ Оплата картой временно недоступна.", show_alert=True)
        return

    # Сохраняем данные о товаре в FSM и запрашиваем email
    await state.set_state(PaymentFSM.waiting_email)
    await state.update_data(
        product_type=product_type,
        product_key=product_key,
        price=info["price"],
        label=info["label"],
    )

    back_cb = "menu:plans" if product_type == "plan" else "buy:oneoff"
    await callback.message.edit_text(
        f"💳 *{info['label']}* — {info['price']} ₽\n\n"
        f"Введите ваш *email* для получения чека об оплате:\n\n"
        f"_Например: example@mail.ru_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)],
        ]),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(PaymentFSM.waiting_email)
async def receive_email_for_payment(message: Message, user: User, state: FSMContext):
    email = (message.text or "").strip()

    if not _valid_email(email):
        await message.answer(
            "❌ Некорректный email. Попробуйте ещё раз:\n\n_Например: example@mail.ru_",
            parse_mode="Markdown",
        )
        return

    data = await state.get_data()
    product_type = data["product_type"]
    product_key = data["product_key"]
    label = data["label"]
    price = data["price"]
    await state.clear()

    from bot.services.yookassa_service import create_payment
    desc = PRODUCT_DESCRIPTIONS.get(product_key, label)
    amount = float(price)

    wait_msg = await message.answer("⏳ Создаём ссылку на оплату...")

    try:
        payment = await create_payment(
            shop_id=settings.yookassa_shop_id,
            secret_key=settings.yookassa_secret_key,
            amount=amount,
            description=desc,
            return_url=settings.yookassa_return_url,
            email=email,
            metadata={
                "user_id": str(user.telegram_id),
                "product_type": product_type,
                "product_key": product_key,
            },
        )
    except Exception as e:
        logger.error("YooKassa create_payment failed: %s", e, exc_info=True)
        await wait_msg.edit_text("❌ Ошибка при создании платежа. Попробуйте позже.")
        return

    back_cb = "menu:plans" if product_type == "plan" else "buy:oneoff"
    await wait_msg.edit_text(
        f"💳 *{label}* — {price} ₽\n\n"
        f"Нажмите кнопку ниже для перехода на страницу оплаты.\n"
        f"После оплаты вернитесь в бот — доступ откроется автоматически.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment["confirmation_url"])],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb)],
        ]),
        parse_mode="Markdown",
    )


# ─── Шаг 2а (legacy): выбрана оплата картой → список методов ─────────────────

@router.callback_query(F.data.startswith("pay:card:"))
async def card_method_menu(callback: CallbackQuery):
    # pay:card:plan:lite  или  pay:card:product:full_matrix
    parts = callback.data.split(":")  # ['pay', 'card', type, key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    label = info["label"] if info else product_key
    price = info["price"] if info else "—"

    await callback.message.edit_text(
        f"💳 *Оплата картой — {label}* ({price} ₽)\n\nВыбери удобный способ:",
        reply_markup=card_methods_keyboard(product_type, product_key),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Шаг 2б: выбран конкретный карточный метод → счёт через провайдера ───────

@router.callback_query(F.data.startswith("pay:sbp:") | F.data.startswith("pay:card_visa:") | F.data.startswith("pay:ymoney:"))
async def card_pay_invoice(callback: CallbackQuery, user: User):
    parts = callback.data.split(":")  # ['pay', method, type, key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Товар не найден")
        return

    if not settings.payment_provider_token:
        await callback.answer(
            "⚠️ Оплата картой временно недоступна. Используй Telegram Stars.",
            show_alert=True,
        )
        return

    label = info["label"]
    price_kopecks = info["price"] * 100  # Telegram: сумма в копейках для рублей

    payload = f"{product_type}:{product_key}"
    desc = PRODUCT_DESCRIPTIONS.get(product_key, label)

    await callback.message.answer_invoice(
        title=label,
        description=desc,
        payload=payload,
        provider_token=settings.payment_provider_token,
        currency="RUB",
        prices=[LabeledPrice(label=label, amount=price_kopecks)],
    )
    await callback.answer()


# ─── Шаг 2б альт: выбраны Stars → счёт ───────────────────────────────────────

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


# ─── Навигация: назад к методам оплаты (из выбора карточной системы) ─────────

@router.callback_query(F.data.startswith("pay:method:"))
async def back_to_pay_method(callback: CallbackQuery):
    parts = callback.data.split(":")  # ['pay', 'method', type, key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    info = PLAN_DISPLAY.get(product_key) or PRODUCT_DISPLAY.get(product_key)
    label = info["label"] if info else product_key
    price = info["price"] if info else "—"

    back_cb = "menu:plans" if product_type == "plan" else "buy:oneoff"
    period = info.get("period", "") if product_type == "plan" else ""
    suffix = f" / {period}" if period else ""

    await callback.message.edit_text(
        f"🛒 *{label}* — {price} ₽{suffix}\n\nВыбери способ оплаты:",
        reply_markup=payment_method_keyboard(product_type, product_key, price, back_cb),
        parse_mode="Markdown",
    )
    await callback.answer()


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

    await _process_referral_reward(session, user, message.bot)
    await session.commit()


# ─── Вспомогательные ──────────────────────────────────────────────────────────

async def _activate_subscription(session: AsyncSession, user: User, plan_key: str):
    plan = PLANS.get(plan_key)
    if not plan:
        return
    days = plan.get("days", 30)
    expires = datetime.now(timezone.utc) + timedelta(days=days)

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

    from bot.services.limits import get_or_create_usage
    usage = await get_or_create_usage(session, user.id)
    for field in ("ai_messages", "personal_questions", "weekly_reports",
                  "compatibility", "daily_forecasts", "mini_readings", "date_selections"):
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
