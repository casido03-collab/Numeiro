"""Retryable results for the existing VK conversational checkout."""
import json
import random
import time
from uuid import uuid4
from bot.services.cache import get_redis
from bot.services.ai_service import AIUnavailable
from bot.business_dialog.services import generate_business
from bot.prompts.prompts import CLARIFICATION_PROMPT


async def stable_card(redis, key, cards):
    existing = await redis.get(key)
    if not existing:
        await redis.set(key, json.dumps(random.choice(cards), ensure_ascii=False), nx=True)
        existing = await redis.get(key)
    return json.loads(existing)


async def vk_clarification(uid, question):
    r = await get_redis()
    raw = await r.get(f"vk:q29:{uid}")
    if not raw:
        return "Срок уточнения истёк. Готовый ответ: /last_reading. Новый вопрос за 29 ₽: /new_question."
    order = json.loads(raw)
    payment_id = order["payment_id"]
    result_key = f"paid_answer:vk:clarification:{payment_id}"
    existing = await r.get(result_key)
    if existing:
        return "Уточнение уже использовано. Сохранённый ответ:\n\n" + existing + "\n\nНовая тема: /new_question (29 ₽)."
    if time.time() > order["created_at"] + 86400:
        return "24 часа для уточнения истекли. Исходный ответ доступен по команде /last_reading."
    if not 5 <= len(question.strip()) <= 1000:
        return "Напишите уточнение к исходному ответу — от 5 до 1000 символов."
    lock = f"vk:clarification:lock:{payment_id}"
    token = uuid4().hex
    if not await r.set(lock, token, nx=True, ex=240):
        return "Предыдущее уточнение ещё готовится. Дождитесь ответа."
    try:
        answer = await r.get(f"paid_answer:vk:payment:{payment_id}")
        if not answer:
            raise AIUnavailable("Original paid answer is not available")
        return await generate_business(CLARIFICATION_PROMPT("ru"), json.dumps({
            "original_question": order["question"], "original_answer": answer,
            "clarification": question}, ensure_ascii=False), "medium", 1600,
            cache_key=f"vk:clarification:{payment_id}")
    finally:
        await r.eval("if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0", 1, lock, token)
