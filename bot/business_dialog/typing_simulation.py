"""Симуляция печатания — send_chat_action + задержка перед каждым ответом.

Telegram показывает "печатает..." только 5 секунд после каждого send_chat_action.
Поэтому для длинных пауз мы повторяем action каждые 4 секунды — индикатор
не гаснет, и выглядит как живой непрерывный набор текста.
"""
import asyncio
import random
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)

# Интервал переотправки typing action — чуть меньше 5 сек лимита Telegram
_REFRESH_INTERVAL = 4.0


async def _typing(bot: Bot, chat_id: int, biz_conn_id: str | None, seconds: float) -> None:
    """Держать индикатор 'печатает...' ровно seconds секунд.
    Повторяет send_chat_action каждые 4 сек чтобы индикатор не гас."""
    kwargs: dict = {"chat_id": chat_id, "action": "typing"}
    if biz_conn_id:
        kwargs["business_connection_id"] = biz_conn_id

    elapsed = 0.0
    while elapsed < seconds:
        try:
            await bot.send_chat_action(**kwargs)
        except Exception as e:
            logger.debug("typing action failed: %s", e)
        # Спим не дольше оставшегося времени
        sleep_for = min(_REFRESH_INTERVAL, seconds - elapsed)
        await asyncio.sleep(sleep_for)
        elapsed += sleep_for


# ─── Фиксированные паузы ──────────────────────────────────────────────────────

async def typing_short(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """1.5–2.5 сек: системные сообщения, подтверждения."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(1.5, 2.5))


async def typing_medium(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """3–5 сек: средние сообщения, переходы."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(3.0, 5.0))


async def typing_long(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """6–10 сек: после оплаты — 'готовлю разбор'."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(6.0, 10.0))


async def typing_deflect(bot: Bot, chat_id: int, biz_conn_id: str | None = None) -> None:
    """8–18 сек: deflect-сообщения — имитация занятости."""
    await _typing(bot, chat_id, biz_conn_id, random.uniform(8.0, 18.0))


# ─── Динамическая пауза по длине текста ───────────────────────────────────────

def _calc_typing_seconds(text: str) -> float:
    """Рассчитать реалистичное время набора текста.

    Логика:
    - Базовое время на обдумывание: 1.5–3 сек
    - Скорость набора: ~4 символа в секунду (средний мессенджер-темп)
    - Лёгкое случайное отклонение ±15%
    - Потолок 22 сек — дольше ждать некомфортно
    """
    chars       = len(text)
    think_pause = random.uniform(1.5, 3.0)        # пауза перед началом набора
    type_time   = chars / 4.0                      # ~4 символа/сек
    total       = think_pause + type_time
    jitter      = random.uniform(0.85, 1.15)       # ±15% живости
    return min(total * jitter, 22.0)               # не дольше 22 сек


async def typing_for_text(bot: Bot, chat_id: int, biz_conn_id: str | None, text: str) -> None:
    """Задержка точно под длину текста — индикатор не гаснет на протяжении всего времени."""
    seconds = _calc_typing_seconds(text)
    await _typing(bot, chat_id, biz_conn_id, seconds)
