"""Платежи — Telegram Stars + Yookassa (карта/СБП)."""
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
from bot.models.user import User, Payment
from bot.keyboards.main import back_to_main
from bot.i18n.translations import t
from config import settings, PRODUCTS

router = Router()
logger = logging.getLogger(__name__)


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


# Централизованный реестр продуктов — используется payments + webhook
from config import VIP_PLAN
PRODUCT_DISPLAY = {key: {"label": item["name"], **item} for key, item in PRODUCTS.items()}
PRODUCT_DISPLAY["vip"] = {"label": "VIP — 30 дней", **VIP_PLAN}

# Оставляем для обратной совместимости с yookassa_webhook.py
PLAN_DISPLAY: dict = {}


class PaymentFSM(StatesGroup):
    waiting_email = State()


# ─── Stars: buy:product:{key} → прямой инвойс ─────────────────────────────────

@router.callback_query(F.data.startswith("buy:product:"))
async def buy_product_stars(callback: CallbackQuery):
    product_key = callback.data.split(":")[-1]
    await _send_stars_invoice(callback, "product", product_key)


# ─── Stars: pay:stars:product:{key} → инвойс ──────────────────────────────────

@router.callback_query(F.data.startswith("pay:stars:"))
async def stars_pay_invoice(callback: CallbackQuery, user: User):
    parts = callback.data.split(":")  # ['pay', 'stars', 'product', key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]
    await _send_stars_invoice(callback, product_type, product_key)


async def _send_stars_invoice(callback: CallbackQuery, product_type: str, product_key: str):
    info = PRODUCT_DISPLAY.get(product_key)
    if not info:
        await callback.answer("❌ Товар не найден")
        return
    label = info["label"]
    stars = info["price_stars"]
    payload = f"{product_type}:{product_key}"
    await callback.message.answer_invoice(
        title=label,
        description=label,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=label, amount=stars)],
    )
    await callback.answer()


# ─── Card: pay:card:product:{key} → спрашиваем email ─────────────────────────

@router.callback_query(F.data.startswith("pay:card:"))
async def card_pay_ask_email(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    parts = callback.data.split(":")  # ['pay', 'card', 'product', key]
    if len(parts) < 4:
        await callback.answer()
        return
    product_type, product_key = parts[2], parts[3]

    await state.set_state(PaymentFSM.waiting_email)
    await state.update_data(product_type=product_type, product_key=product_key, lang=lang)

    _ask = t("pay_ask_email", lang)
    await callback.message.edit_text(
        _ask,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="menu:main")]
        ]),
    )
    await callback.answer()


@router.message(PaymentFSM.waiting_email)
async def card_pay_create(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    fsm = await state.get_data()
    lang = fsm.get("lang", "ru")

    if not _valid_email(email):
        _bad = t("pay_email_invalid", lang)
        await message.answer(_bad)
        return

    product_type = fsm.get("product_type", "product")
    product_key  = fsm.get("product_key", "")
    await state.clear()

    info = PRODUCT_DISPLAY.get(product_key)
    if not info:
        await message.answer("❌ Товар не найден")
        return

    price = info["price_rub"]
    label = info["label"]

    thinking = await message.answer(t("pay_creating", lang))

    try:
        from bot.services.yookassa_service import create_payment
        payment = await create_payment(
            shop_id=settings.yookassa_shop_id,
            secret_key=settings.yookassa_secret_key,
            amount=float(price),
            description=f"Aisha AI — {label}",
            return_url=settings.yookassa_return_url,
            metadata={
                "user_id":      str(message.from_user.id),
                "product_type": product_type,
                "product_key":  product_key,
            },
            email=email,
        )
        link = payment["confirmation_url"]
        text = t("pay_link_created", lang).format(name=label, price=price, link=link)
        await thinking.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.error("Yookassa payment creation failed: %s", e)
        await thinking.edit_text(t("pay_error", lang))


# ─── Telegram pre-checkout ────────────────────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    parts = pre_checkout_query.invoice_payload.split(":", 1)
    info = PRODUCT_DISPLAY.get(parts[-1])
    valid = (len(parts) == 2 and parts[0] == "product" and info is not None
             and pre_checkout_query.currency == "XTR"
             and pre_checkout_query.total_amount == info["price_stars"])
    await pre_checkout_query.answer(ok=valid, error_message=None if valid else "Счёт устарел. Откройте оплату заново из меню.")


# ─── Успешная оплата Stars ────────────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment(message: Message, user: User, session: AsyncSession):
    payment = message.successful_payment
    payload  = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id

    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    existing = await session.scalar(select(Payment.id).where(Payment.telegram_payment_charge_id == charge_id))
    if existing:
        await message.answer("Этот платёж уже зачислен. Готовые результаты доступны в «Мои разборы».")
        return
    parts = payload.split(":", 1)
    product_key = parts[-1]
    info = PRODUCT_DISPLAY.get(product_key)
    if not info or payment.currency != "XTR" or payment.total_amount != info["price_stars"]:
        raise ValueError("Unexpected Stars payment")

    session.add(Payment(
        user_id=user.id,
        telegram_payment_charge_id=charge_id,
        amount=payment.total_amount,
        currency=payment.currency,
        product_type=payload,
        status="completed",
    ))

    parts = payload.split(":", 1)
    product_key = parts[1] if len(parts) > 1 else payload

    await _activate_one_time_product(user, product_key, event_id=f"stars:{charge_id}")

    info = PRODUCT_DISPLAY.get(product_key, {})
    label = info.get("label", product_key)

    await _process_referral_reward(session, user, message.bot)
    await session.commit()
    await message.answer(
        f"✅ *{label}* — оплачено! 🌟\n\nМожете использовать раздел прямо сейчас.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Использовать сейчас", callback_data=_product_callback(product_key))]
        ]),
    )



# ─── Вспомогательные ──────────────────────────────────────────────────────────

async def _activate_one_time_product(user: User, product_key: str, event_id: str | None = None):
    if product_key == "vip":
        from bot.services.limits import activate_vip
        await activate_vip(user.id, days=30, event_id=event_id)
    else:
        from bot.services.limits import add_credit
        await add_credit(user.id, product_key, event_id=event_id)


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

    ref.reward_given = True
    ref.purchase_status = True

    # Считаем общее число рефералов пригласителя
    from sqlalchemy import func
    total_res = await session.execute(
        select(func.count()).where(Referral.inviter_telegram_id == user.invited_by)
    )
    total_refs = total_res.scalar() or 0

    from bot.handlers.referral import REFERRAL_LEVELS
    from bot.services.limits import add_credit, activate_vip
    from bot.services.cache import get_redis

    r = await get_redis()
    rewards_given = []

    for threshold, level_name, rewards in REFERRAL_LEVELS:
        if total_refs < threshold:
            break
        level_key = f"ref_level:{threshold}:{inviter.id}"
        already = await r.get(level_key)
        if already:
            continue
        for product_key, amount in rewards:
            if product_key == "vip_days":
                await activate_vip(inviter.id, days=amount, event_id=f"ref:{threshold}:{inviter.id}:vip")
                rewards_given.append(f"👑 {amount} дня VIP")
            else:
                await add_credit(inviter.id, product_key, amount, event_id=f"ref:{threshold}:{inviter.id}:{product_key}")
                label = PRODUCT_DISPLAY.get(product_key, {}).get("label", product_key)
                rewards_given.append(f"✨ {label} ×{amount}")

        await r.set(level_key, "1")

    if rewards_given:
        rewards_text = "\n".join(rewards_given)
        try:
            await bot.send_message(
                inviter.telegram_id,
                f"🎁 *Новый уровень рефералов!*\n\n"
                f"👥 Друзей приглашено: *{total_refs}*\n\n"
                f"Твои награды:\n{rewards_text}",
                parse_mode="Markdown",
            )
        except Exception:
            pass
    elif total_refs == 1 or ref.purchase_status:
        try:
            await bot.send_message(
                inviter.telegram_id,
                f"👥 Твой друг зарегистрировался! Всего приглашено: *{total_refs}*",
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
        "tarot_card":        "menu:tarot",
        "mini_reading":      "menu:reading",
        "vip":               "cabinet:open",
    }.get(product_key, "menu:main")


# ─── VIP Продление ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "pay:vip:renew")
async def vip_renew(callback: CallbackQuery, user: User, lang: str = "ru"):
    from bot.keyboards.main import payment_method_keyboard as _pay_kb
    from bot.services.cache import get_redis
    from zoneinfo import ZoneInfo
    remaining = max(0, await (await get_redis()).ttl(f"vip:{user.id}"))
    until = datetime.now(ZoneInfo("Europe/Moscow")) + timedelta(seconds=remaining, days=30)
    terms = {
        "ru": f"VIP — 1 999 ₽ / 1 999 ⭐. При оплате сейчас срок будет до {until:%d.%m.%Y %H:%M} МСК.\n\nДобавятся 30 дней и новый пакет разборов. Остаток сохранится до общего окончания VIP. Автосписания нет.",
        "en": f"VIP — 1,999 ⭐. Paying now extends access until {until:%d.%m.%Y %H:%M} Moscow time. Adds 30 days and a new quota package; unused readings carry over until expiry. No automatic charges.",
        "fa": f"VIP — 1999 ⭐. با پرداخت اکنون تا {until:%d.%m.%Y %H:%M} به وقت مسکو فعال می‌شود. ۳۰ روز و سهمیه جدید اضافه می‌شود؛ مانده حفظ می‌شود. برداشت خودکار ندارد.",
        "tr": f"VIP — 1999 ⭐. Şimdi ödeme ile {until:%d.%m.%Y %H:%M} Moskova saatine kadar uzar. 30 gün ve yeni kota eklenir; kalan haklar korunur. Otomatik ödeme yok.",
    }.get(lang)
    await callback.message.edit_text(
        terms,
        reply_markup=_pay_kb("vip", 1999, 1999, lang, back="cabinet:open"),
        parse_mode="Markdown",
    )
    await callback.answer()
