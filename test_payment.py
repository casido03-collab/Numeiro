"""Симуляция webhook-оплаты для тестирования.
Запускать на сервере: python test_payment.py
"""
import asyncio
import hmac
import hashlib
import json
import sys

TELEGRAM_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1715461306
AMOUNT      = int(sys.argv[2]) if len(sys.argv) > 2 else 190
PURCHASE_ID = "test_pay_001"


async def main():
    # Подключаем окружение проекта
    from config import settings
    from bot.services.cache import get_redis
    from bot.services.database import async_session_maker
    from bot.business_dialog.tribute_flow import _process_payment

    print(f"Simulating payment: tg_id={TELEGRAM_ID}, amount={AMOUNT}")

    # Дедупликация — сбрасываем ключ чтобы повторные тесты работали
    r = await get_redis()
    await r.delete(f"trib_paid:{PURCHASE_ID}")

    async with async_session_maker() as session:
        await _process_payment(
            session,
            telegram_id=TELEGRAM_ID,
            payment_id=PURCHASE_ID,
            amount=AMOUNT,
            product_id="",
        )

    print("Done.")

asyncio.run(main())
