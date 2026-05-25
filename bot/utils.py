"""Утилиты: безопасная отправка сообщений, парсинг дат, clean UX helpers.

Два уровня отправки Telegram API:
  • «Быстрые» (меню, статичные разделы) — request_timeout=3s, без лишнего retry.
    Цель: 0.5–2 сек в норме, не более 7.5 сек в худшем случае.
  • «Обычные» (AI-ответы, важная доставка) — request_timeout используется по умолчанию
    сессии (8s), retry за счёт ResilientSession.

ВАЖНО: _with_retry из utils.py НЕ используется в safe_answer/safe_edit — там retry
уже делает ResilientSession. Двойной retry создавал стек до 55 секунд.
"""
import asyncio
import logging
import time
from datetime import date, datetime
from typing import Optional

from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)

# ─── Timeout-константы ────────────────────────────────────────────────────────
_MENU_TIMEOUT = 3   # секунд: для меню/статичных разделов (без AI)
_AI_TIMEOUT   = 15  # секунд: для доставки AI-ответа (явный override)


# ─── Парсинг дат ─────────────────────────────────────────────────────────────

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


# ─── Быстрые функции для меню (timeout=3s) ───────────────────────────────────

async def safe_answer_menu(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Быстрая отправка для меню: request_timeout=3s.
    Retry делает ResilientSession (1 попытка → max 3+1.5+3 = 7.5s).
    При ошибке возвращает None, не бросает исключение.
    """
    try:
        return await message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            request_timeout=_MENU_TIMEOUT,
        )
    except TelegramBadRequest as e:
        if "can't parse" in str(e).lower():
            try:
                return await message.answer(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=None,
                    request_timeout=_MENU_TIMEOUT,
                )
            except Exception as e2:
                logger.warning("safe_answer_menu: plain-text fallback failed: %s", e2)
        else:
            logger.warning("safe_answer_menu: bad request: %s", e)
    except Exception as e:
        logger.warning("safe_answer_menu: failed: %s", e)
    return None


async def safe_edit_menu(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Быстрое редактирование для меню: request_timeout=3s.
    Если редактировать нельзя — fallback на safe_answer_menu.
    """
    try:
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            request_timeout=_MENU_TIMEOUT,
        )
    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "can't parse" in err_lower:
            try:
                return await message.edit_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=None,
                    request_timeout=_MENU_TIMEOUT,
                )
            except TelegramBadRequest:
                pass
        # Сообщение нельзя редактировать — отправить новое
        logger.debug("safe_edit_menu: edit failed (%s), falling back to answer", e)
        return await safe_answer_menu(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning("safe_edit_menu: failed: %s", e)
    return None


# ─── Обычные функции (таймаут по умолчанию сессии = 8s) ───────────────────────

async def safe_answer(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Отправить сообщение. Retry на уровне ResilientSession (не дублировать здесь).
    При Markdown-ошибке — повтор без parse_mode.
    При любой неустранимой ошибке — None.
    """
    try:
        return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
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
    Редактировать сообщение. Fallback на safe_answer если редактировать нельзя.
    Для доставки AI-ответов используй safe_edit_ai() (увеличенный timeout).
    """
    try:
        return await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "can't parse" in err_lower:
            try:
                return await message.edit_text(text, reply_markup=reply_markup, parse_mode=None)
            except TelegramBadRequest:
                pass
        logger.debug("safe_edit: edit failed (%s), falling back to answer", e)
        return await safe_answer(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning("safe_edit: failed: %s", e)
    return None


async def safe_edit_ai(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Доставка AI-ответа: request_timeout=15s (явный override).
    Fallback на safe_answer если редактировать нельзя.
    """
    try:
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            request_timeout=_AI_TIMEOUT,
        )
    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "can't parse" in err_lower:
            try:
                return await message.edit_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=None,
                    request_timeout=_AI_TIMEOUT,
                )
            except TelegramBadRequest:
                pass
        logger.debug("safe_edit_ai: edit failed (%s), falling back to answer", e)
        return await safe_answer(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning("safe_edit_ai: failed: %s", e)
    return None


async def replace_message(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Optional[Message]:
    """
    Универсальная замена сообщения на текст.
    - Фото/видео/документ: сначала удаляем, затем отправляем новое текстовое.
    - Текстовое: редактируем на месте.
    Используется при навигации из медиа-сообщений (карта дня и т.д.).
    """
    if message.photo or message.video or message.document or message.animation:
        try:
            await message.delete()
        except Exception:
            pass
        return await safe_answer(message, text, reply_markup=reply_markup, parse_mode=parse_mode)
    return await safe_edit(message, text, reply_markup=reply_markup, parse_mode=parse_mode)


async def safe_delete(message: Message, timeout: float = 3.0) -> None:
    """Удалить сообщение с таймаутом и тихим игнорированием ошибок."""
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
    fast: bool = False,
) -> Optional[Message]:
    """
    Управляет единственным «меню-сообщением» в чате.

    force_new=True  — всегда отправить новое сообщение.
    force_new=False — попытаться отредактировать отслеживаемое сообщение на месте.
    fast=True       — использовать request_timeout=3s (для меню без AI).
    """
    from bot.services.menu_tracker import get_menu_msg_id, set_menu_msg_id

    req_timeout = _MENU_TIMEOUT if fast else None

    if not force_new:
        old_id = await get_menu_msg_id(telegram_id)
        if old_id:
            edited = None
            try:
                edit_kwargs: dict = dict(
                    text=text,
                    chat_id=message.chat.id,
                    message_id=old_id,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                if req_timeout:
                    edit_kwargs["request_timeout"] = req_timeout
                edited = await message.bot.edit_message_text(**edit_kwargs)
            except TelegramBadRequest:
                # Сообщение нельзя редактировать — удалить и отправить новое
                try:
                    del_kwargs: dict = dict(chat_id=message.chat.id, message_id=old_id)
                    if req_timeout:
                        del_kwargs["request_timeout"] = req_timeout
                    await asyncio.wait_for(
                        message.bot.delete_message(**del_kwargs), timeout=3.0
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning("show_menu_message: edit failed, sending new: %s", e)

            if edited is not None:
                return edited

    # Отправить новое сообщение
    if fast:
        new_msg = await safe_answer_menu(
            message, text, reply_markup=reply_markup, parse_mode=parse_mode
        )
    else:
        new_msg = await safe_answer(
            message, text, reply_markup=reply_markup, parse_mode=parse_mode
        )

    if new_msg:
        await set_menu_msg_id(telegram_id, new_msg.message_id)
    return new_msg


async def ensure_keyboard(message: Message, telegram_id: int) -> None:
    """
    Отправить постоянную reply-клавиатуру ровно один раз за всё время жизни пользователя.
    """
    from bot.services.menu_tracker import is_keyboard_shown, mark_keyboard_shown
    from bot.keyboards.reply import main_reply_keyboard

    if not await is_keyboard_shown(telegram_id):
        sent = await safe_answer_menu(
            message, "🌙", reply_markup=main_reply_keyboard(), parse_mode=None
        )
        if sent:
            await mark_keyboard_shown(telegram_id)
