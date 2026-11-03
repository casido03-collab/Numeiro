"""A YooKassa payment is bound to one owner, frozen service and quoted amount."""
from decimal import Decimal
from sqlalchemy import select
from config import settings, PRODUCTS, VIP_PLAN
from bot.models.vk import VKOrder, VKInbox
from bot.models.user import Payment
from bot.services.limits import add_credit, activate_vip
from bot.services.yookassa_service import create_payment, validate_payment, verified_payment


async def checkout(session, order, email):
    if order.status in ("paid", "fulfilled"):
        return None
    if order.checkout_url and order.status == "pending":
        return order.checkout_url
    if order.status == "canceled":
        raise ValueError("Canceled order")
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        raise RuntimeError("YooKassa not configured")
    # Persist receipt data before the request: retries use exactly the same body.
    order.email = order.email or email
    await session.commit()
    label = "VIP на 30 дней" if order.product == "vip" else PRODUCTS[order.product]["name"]
    payment = await create_payment(settings.yookassa_shop_id, settings.yookassa_secret_key,
        order.amount, f"Aisha AI — {label}", "https://vk.me/babushkaaisha",
        {"platform": "vk_catalog", "product_type": "product", "product_key": order.product,
         "vk_user_id": str(order.vk_id), "user_id": str(order.user_id), "order_id": order.id},
        email=order.email, idempotency_key=order.id)
    order.payment_id = payment["id"]
    order.checkout_url = payment["confirmation_url"]
    order.status = "pending"
    await session.commit()
    return order.checkout_url


async def accept_payment(maker, payment):
    if not validate_payment(payment) or payment.get("metadata", {}).get("platform") != "vk_catalog":
        raise ValueError("Invalid VK payment")
    meta = payment["metadata"]
    async with maker() as session:
        order = await session.scalar(select(VKOrder).where(VKOrder.id == meta.get("order_id")).with_for_update())
        if (not order or str(order.vk_id) != meta.get("vk_user_id") or str(order.user_id) != meta.get("user_id")
                or order.product != meta.get("product_key") or Decimal(str(order.amount)) != Decimal(payment["amount"]["value"])
                or (order.payment_id and order.payment_id != payment["id"])):
            raise ValueError("Payment does not match order")
        if order.status in ("paid", "fulfilled"):
            return
        event_key = f"vk-yk:{payment['id']}"
        if order.product == "vip":
            await activate_vip(order.user_id, VIP_PLAN["duration_days"], event_id=event_key)
        else:
            await add_credit(order.user_id, order.product, event_id=event_key)
        order.payment_id, order.status = payment["id"], "paid"
        session.add(Payment(user_id=order.user_id, telegram_payment_charge_id=payment["id"],
                            amount=order.amount*100, currency="RUB", product_type=f"vk:{order.product}", status="completed"))
        session.add(VKInbox(event_key=event_key, vk_id=order.vk_id, message={"internal": "paid", "order_id": order.id}))
        await session.commit()


async def check_order(maker, order):
    if not order.payment_id:
        return "draft"
    payment = await verified_payment(order.payment_id)
    if payment["status"] == "succeeded":
        await accept_payment(maker, payment)
    elif payment["status"] == "canceled":
        async with maker() as session:
            current = await session.get(VKOrder, order.id)
            if current.status == "pending":
                current.status = "canceled"
                await session.commit()
    return payment["status"]
