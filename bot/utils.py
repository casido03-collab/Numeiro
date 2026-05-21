"""Утилиты: безопасная отправка Markdown, парсинг дат, clean UX helpers."""
import re
import logging
from datetime import date, datetime
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


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


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Message:
    """
    Edit message with Markdown; if Telegram rejects it (bad entities),
    retry without parse_mode to never lose the response.
    """
    try:
        return await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "can't parse" in str(e).lower() or "bad request" in str(e).lower():
            logger.warning("Markdown parse error, retrying as plain text: %s", e)
            return await message.edit_text(text, reply_markup=reply_markup, parse_mode=None)
        raise


async def safe_answer(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = "Markdown",
) -> Message:
    """Answer a message with Markdown; fallback to plain text on parse error."""
    try:
        return await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "can't parse" in str(e).lower() or "bad request" in str(e).lower():
            logger.warning("Markdown parse error, retrying as plain text: %s", e)
            return await message.answer(text, reply_markup=reply_markup, parse_mode=None)
        raise


# ─── Clean UX helpers ─────────────────────────────────────────────────────────

async def show_menu_message(
    message: Message,
    telegram_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "Markdown",
    force_new: bool = False,
) -> Message:
    """
    Manage the single tracked "menu" message in the chat.

    force_new=True  →  always send a fresh message.answer() and track it.
                       Use for /start and any Message-triggered entry points
                       where editing a stale tracked message would place the
                       response far above the new command in the chat.

    force_new=False →  try to EDIT the previously tracked message in-place
                       (silent, no scroll jump).  If edit fails, send new.
                       Use for reply-keyboard button handlers.

    Does NOT delete the caller's trigger message — that is done by the
    reply-keyboard handlers themselves before calling this function.
    """
    from bot.services.menu_tracker import get_menu_msg_id, set_menu_msg_id

    if not force_new:
        # ── Try editing the existing tracked menu message ───────────────────
        old_id = await get_menu_msg_id(telegram_id)
        if old_id:
            try:
                edited = await message.bot.edit_message_text(
                    text,
                    chat_id=message.chat.id,
                    message_id=old_id,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                # Edit succeeded — tracked ID unchanged, nothing else to do
                return edited
            except Exception:
                # Edit failed — remove stale message silently
                try:
                    await message.bot.delete_message(message.chat.id, old_id)
                except Exception:
                    pass

    # ── Send a brand-new message and track its ID ───────────────────────────
    new_msg = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await set_menu_msg_id(telegram_id, new_msg.message_id)
    return new_msg


async def ensure_keyboard(message: Message, telegram_id: int) -> None:
    """
    Send the persistent reply keyboard exactly once per user lifetime.

    Subsequent calls are no-ops (checked via Redis flag).
    """
    from bot.services.menu_tracker import is_keyboard_shown, mark_keyboard_shown
    from bot.keyboards.reply import main_reply_keyboard

    if not await is_keyboard_shown(telegram_id):
        await message.answer("🌙", reply_markup=main_reply_keyboard())
        await mark_keyboard_shown(telegram_id)
