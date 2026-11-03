"""Anti-free-chat система — мягкие ответы для занятой бабушки Аиши."""
import random

SOFT_DEFLECTS = [
    "Мы уже обсудили запрос в ознакомительном диалоге. Подробный разбор — отдельная платная услуга; состав и цена указаны в предложении.",
    "Для продолжения нужен оплаченный разбор. Вы можете сначала посмотреть условия и решить, подходит ли вам формат. 🌙",
    "Знакомство не включает полный разбор. Если хотите продолжить, выберите предложенную услугу; это необязательно.",
]

# Сколько бесплатных AI-ответов до включения deflect-режима
FREE_MSG_LIMIT = 7


async def get_deflect_message(telegram_id: int) -> str:
    """Вернуть случайный soft-deflect, не повторяя предыдущий."""
    from bot.business_dialog.session_manager import get_last_deflect, set_last_deflect
    last = await get_last_deflect(telegram_id)
    candidates = [i for i in range(len(SOFT_DEFLECTS)) if i != last]
    idx = random.choice(candidates)
    await set_last_deflect(telegram_id, idx)
    return SOFT_DEFLECTS[idx]
