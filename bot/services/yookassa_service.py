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
) -> dict:
    from yookassa import Payment
    _configure(shop_id, secret_key)
    idempotency_key = str(uuid.uuid4())
    payment = Payment.create(
        {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": metadata,
        },
        idempotency_key,
    )
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
    )
