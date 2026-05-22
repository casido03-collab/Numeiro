"""Утилиты: безопасная отправка Markdown, парсинг дат, clean UX helpers."""
import asyncio
import logging
from datetime import date, datetime
from typing import Optional
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)

# Retry-настройки для Telegram API вызовов
_RETRIES = 2          # попыток после первой неудачи
_RETRY_DELAY = 1.5    # секунд между попытками


def parse_birth_date(birth_str: str | None) -> date | None:
    """Parse birth date from stored string or user input."""
    if not birth_str:
        return None
    for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(birth_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ─── Retry-хелпер ─────────────────────────────────────────────────────────────

async def _with_retry(fn, label: str = "telegram call"):
    """
    Вызвать callable fn() с retry при сетевых ошибках Telegram.

    - TelegramNetworkError → до _RETRIES повторов с паузой _RETRY_DELAY сек.
    - TelegramRetryAfter   → ждать retry_after секунд, затем повтор.
    - Другие исключения    → пробрасываются без retry.
    """
    last_err = None
    for attempt in range(_RETRIES + 1):
        try:
            return await fn()
        except TelegramRetryAfter as e:
            wait = e.retry_after + 1
            logger.warning("%s: RetryAfter %ss (attempt %d)", label, wait, attempt + 1)
            await asyncio.sleep(wait)
        except TelegramNetworkError as e:
            last_err = e
            logger.warning("%s: network error (attempt %d/%d): %s", label, attempt + 1, _RETRIES + 1, e)
            if attempt < _RETRIES:
                await asyncio.sleep(_RETRY_DELAY)
    logger.error("%s: all %d attempts failed: %s", label, _RETRIES + 1, last_err)
    raise last_err


# ─── Безопасные Telegram API вызовы ──────────────────────────────────────────

async def safe_answer(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Отправить ответное сообщение.
    - Retry при TelegramNetworkError / TelegramRetryAfter.
    - При Markdown-ошибке повтор без parse_mode.
    - При любой неустранимой ошибке возвращает None (не бросает исключение).
    """
    try:
        return await _with_retry(
            lambda: message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode),
            label="safe_answer",
        )
    except TelegramBadRequest as e:
        if "can't parse" in str(e).lower():
            try:
                return await message.answer(text, reply_markup=reply_markup, parse_mode=None)
            except Exception as e2:
                logger.warning("safe_answer: plain-text fallback failed: %s", e2)
        else:
            logger.warning("safe_answer: bad request: %s", e)
    except Exception as e:
        logger.warning("safe_answer: failed: %s", e)
    return None


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Отредактировать сообщение.
    - Retry при TelegramNetworkError / TelegramRetryAfter.
    - При Markdown-ошибке повтор без parse_mode.
    - Если редактирование невозможно (сообщение удалено / слишком старое) —
      fallback на safe_answer (отправляет новое сообщение).
    - Возвращает None если ни edit, ни answer не удались.
    """
    try:
        return await _with_retry(
            lambda: message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode),
            label="safe_edit",
        )
    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "can't parse" in err_lower:
            try:
                return await message.edit_text(text, reply_markup=reply_markup, parse_mode=None)
            except TelegramBadRequest:
                pass  # Всё равно не получилось — идём к fallback
        # Сообщение нельзя редактировать (удалено, слишком старое и т.д.)
        logger.debug("safe_edit: edit failed (%s), falling back to answer", e)
        return await safe_answer(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning("safe_edit: failed: %s", e)
    return None


async def safe_delete(message: Message, timeout: float = 5.0) -> None:
    """
    Удалить сообщение с таймаутом и тихим игнорированием ошибок.
    Таймаут защищает от зависания при зомби-TCP-соединении.
    """
    try:
        await asyncio.wait_for(message.delete(), timeout=timeout)
    except Exception:
        pass


# ─── Clean UX helpers ─────────────────────────────────────────────────────────

async def show_menu_message(
    message: Message,
    telegram_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "Markdown",
    force_new: bool = False,
) -> Optional[Message]:
    """
    Управляет единственным «меню-сообщением» в чате.

    force_new=True  — всегда отправить новое сообщение (для /start и reply-кнопок).
    force_new=False — попытаться отредактировать отслеживаемое сообщение на месте
                      (тихо, без прокрутки вверх). Если не вышло — отправить новое.
    """
    from bot.services.menu_tracker import get_menu_msg_id, set_menu_msg_id

    if not force_new:
        old_id = await get_menu_msg_id(telegram_id)
        if old_id:
            edited = None
            try:
                edited = await _with_retry(
                    lambda: message.bot.edit_message_text(
                        text,
                        chat_id=message.chat.id,
                        message_id=old_id,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode,
                    ),
                    label="show_menu_message:edit",
                )
            except TelegramBadRequest:
                # Сообщение нельзя редактировать — молча удалить
                try:
                    await asyncio.wait_for(
                        message.bot.delete_message(message.chat.id, old_id), timeout=3.0
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning("show_menu_message: edit failed, sending new: %s", e)

            if edited is not None:
                return edited

    # Отправить новое сообщение
    new_msg = await safe_answer(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    if new_msg:
        await set_menu_msg_id(telegram_id, new_msg.message_id)
    return new_msg


async def ensure_keyboard(message: Message, telegram_id: int) -> None:
    """
    Отправить постоянную reply-клавиатуру ровно один раз за всё время жизни пользователя.
    Повторные вызовы — no-op (проверяется через Redis).
    """
    from bot.services.menu_tracker import is_keyboard_shown, mark_keyboard_shown
    from bot.keyboards.reply import main_reply_keyboard

    if not await is_keyboard_shown(telegram_id):
        sent = await safe_answer(message, "🌙", reply_markup=main_reply_keyboard(), parse_mode=None)
        if sent:
            await mark_keyboard_shown(telegram_id)
