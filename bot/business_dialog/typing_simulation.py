"""Симуляция печатания — send_chat_action + задержка перед каждым ответом."""
import asyncio
import random
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


async def _typing(bot: Bot, chat_id: int, biz_conn_id: str | None, seconds: float) -> None:
    try:
        kwargs: dict = {"chat_id": chat_id, "action": "typing"}
        if biz_conn_id:
            kwargs["business_connection_id"] = biz_conn_id
        await bot.send_chat_action(**kwargs)
    except Exception as e:
        logger.debug("typing action failed: %s", e)
    await asyncio.sleep(seconds)


async def typing_short(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """1–2 сек: короткие ответы."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(1.0, 2.0))


async def typing_medium(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """3–5 сек: средние ответы."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(3.0, 5.0))


async def typing_long(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """5–8 сек: после оплаты — генерация разбора."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(5.0, 8.0))


async def typing_deflect(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """10–25 сек: настойчивые бесплатные пользователи — имитация занятости."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(10.0, 25.0))


async def typing_for_text(bot: Bot, chat_id: int, biz_conn_id: str | None, text: str) -> None:
    """Задержка пропорциональная длине ответа — имитирует живой набор."""
    length = len(text)
    if length < 60:
        seconds = random.uniform(2.5, 4.0)
    elif length < 150:
        seconds = random.uniform(4.5, 7.0)
    elif length < 300:
        seconds = random.uniform(7.0, 11.0)
    else:
        seconds = random.uniform(10.0, 16.0)
    await _typing(bot, chat_id, biz_conn_id, seconds)
