"""ЮКасса API — создание и проверка платежей."""
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


def _configure(shop_id: str, secret_key: str):
    from yookassa import Configuration
    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def _create_payment_sync(
    shop_id: str,
    secret_key: str,
    amount: float,
    description: str,
    return_url: str,
    metadata: dict,
    email: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    from yookassa import Payment
    _configure(shop_id, secret_key)
    idempotency_key = idempotency_key or str(uuid.uuid4())

    payload: dict = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }

    if email:
        payload["receipt"] = {
            "customer": {"email": email},
            "items": [{
                "description": description,
                "quantity": "1.00",
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "vat_code": 1,
                "payment_mode": "full_payment",
                "payment_subject": "service",
            }],
        }

    payment = Payment.create(payload, idempotency_key)
    return {
        "id": str(payment.id),
        "confirmation_url": payment.confirmation.confirmation_url,
        "status": payment.status,
    }


async def create_payment(
    shop_id: str,
    secret_key: str,
    amount: float,
    description: str,
    return_url: str,
    metadata: dict,
    email: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Создать платёж в ЮКассе. Возвращает dict с id и confirmation_url."""
    return await asyncio.to_thread(
        _create_payment_sync,
        shop_id,
        secret_key,
        amount,
        description,
        return_url,
        metadata,
        email,
        idempotency_key,
    )


async def verified_payment(payment_id: str) -> dict:
    """Read status and metadata from our merchant account, not from webhook input."""
    from config import settings
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        raise RuntimeError("YooKassa credentials are not configured")
    def fetch():
        from yookassa import Payment
        _configure(settings.yookassa_shop_id, settings.yookassa_secret_key)
        payment = Payment.find_one(payment_id)
        return {"id": payment.id, "status": payment.status, "paid": payment.paid,
                "amount": {"value": str(payment.amount.value), "currency": payment.amount.currency},
                "metadata": dict(payment.metadata or {})}
    return await asyncio.to_thread(fetch)


def validate_payment(payment: dict) -> bool:
    from decimal import Decimal
    from config import PRODUCTS, VIP_PLAN
    from bot.business_dialog.upsell import TIERS
    if payment.get("status") != "succeeded" or payment.get("paid") is not True:
        return False
    amount = payment.get("amount", {})
    if amount.get("currency") != "RUB":
        return False
    meta = payment.get("metadata", {})
    platform = meta.get("platform")
    if platform in ("vk", "tg_business"):
        tier = meta.get("tier_key")
        expected = {"q29": 29, "monthly_990": 990}.get(tier, TIERS.get(tier, {}).get("price"))
    elif platform in (None, "", "tg", "telegram", "vk_catalog") and meta.get("product_type") == "product":
        key = meta.get("product_key")
        expected = VIP_PLAN["price_rub"] if key == "vip" else PRODUCTS.get(key, {}).get("price_rub")
    else:
        return False
    return expected is not None and Decimal(str(amount.get("value", 0))) == Decimal(expected)
