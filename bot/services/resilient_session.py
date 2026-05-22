"""
Устойчивая HTTP-сессия для aiogram.

Переопределяет make_request — единственную точку, через которую проходят
ВСЕ запросы к Telegram API (sendMessage, editMessageText, deleteMessage,
getUpdates и т.д.).

Добавляет автоматический retry при TelegramNetworkError / TelegramRetryAfter,
не требуя изменений ни в одном хендлере.
"""
import asyncio
import logging
from typing import Optional

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType

logger = logging.getLogger(__name__)

_RETRIES = 2        # повторов после первой неудачи
_RETRY_DELAY = 1.5  # секунд между попытками


class ResilientSession(AiohttpSession):
    """
    AiohttpSession с автоматическим retry для всех Telegram API вызовов.

    - TelegramNetworkError (Request timeout, Connection reset и т.д.):
      до _RETRIES повторов с паузой _RETRY_DELAY сек.
    - TelegramRetryAfter (flood control от Telegram):
      ждёт retry_after + 1 сек, затем повтор.
    - Любые другие исключения (TelegramBadRequest и т.д.) пробрасываются без retry.
    """

    async def make_request(
        self,
        bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        last_err: Exception | None = None

        for attempt in range(_RETRIES + 1):
            try:
                return await super().make_request(bot, method, timeout=timeout)

            except TelegramRetryAfter as e:
                wait = e.retry_after + 1
                logger.warning(
                    "Telegram flood control: retry after %ss (method=%s)",
                    wait, type(method).__name__,
                )
                await asyncio.sleep(wait)
                # Считаем как попытку — продолжаем цикл без счётчика attempt

            except TelegramNetworkError as e:
                last_err = e
                logger.warning(
                    "TelegramNetworkError attempt %d/%d (method=%s): %s",
                    attempt + 1, _RETRIES + 1, type(method).__name__, e,
                )
                if attempt < _RETRIES:
                    await asyncio.sleep(_RETRY_DELAY)

        # Все попытки исчерпаны
        logger.error(
            "TelegramNetworkError: all %d attempts failed (method=%s): %s",
            _RETRIES + 1, type(method).__name__, last_err,
        )
        raise last_err
