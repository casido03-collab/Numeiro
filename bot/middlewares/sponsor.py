"""Middleware проверки спонсорской подписки."""
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

# Callback-префиксы которые требуют проверки подписки
_GATED_CALLBACKS = (
    "menu:", "free:", "matrix:", "compat:", "weekly:", "sphere:",
    "horoscope:", "tarot:", "daily:", "question:", "dates:",
    "buy:", "cabinet:", "reports:", "share:", "content:",
)

# Reply-кнопки нижнего меню которые требуют проверки
_GATED_REPLIES = {
    "🔮 Меню", "📚 Интересное", "👥 Друзья", "💎 Подписка",
}


async def _get_sponsor_state() -> dict:
    try:
        from bot.handlers.sponsor import get_sponsor_state
        return await get_sponsor_state()
    except Exception as e:
        logger.warning("SponsorMiddleware: get_sponsor_state failed: %s", e)
        return {"enabled": False, "link": "", "channel": ""}


async def _is_subscribed(bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning("Sponsor check error for %s: %s", user_id, e)
        return False


async def _show_sponsor(event, bot, link: str) -> None:
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from bot.handlers.sponsor import _SPONSOR_TEXT

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подписаться", url=link)],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="sponsor:check")],
    ])

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(_SPONSOR_TEXT, reply_markup=kb)
        except Exception:
            await event.message.answer(_SPONSOR_TEXT, reply_markup=kb)
        await event.answer()
    elif isinstance(event, Message):
        await event.answer(_SPONSOR_TEXT, reply_markup=kb)


class SponsorMiddleware(BaseMiddleware):
    """Проверяет подписку на канал спонсора перед любым действием в меню."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        # Проверяем только Message и CallbackQuery
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        # Получаем состояние спонсора
        sponsor = await _get_sponsor_state()
        if not sponsor["enabled"] or not sponsor["channel"]:
            return await handler(event, data)

        # Определяем нужно ли проверять
        needs_check = False

        if isinstance(event, CallbackQuery):
            cb_data = event.data or ""
            # Проверяем только если это кнопка меню (не sponsor:check сам по себе)
            if cb_data != "sponsor:check" and any(cb_data.startswith(p) for p in _GATED_CALLBACKS):
                needs_check = True

        elif isinstance(event, Message):
            text = event.text or ""
            if text in _GATED_REPLIES:
                needs_check = True

        if not needs_check:
            return await handler(event, data)

        # Проверяем подписку
        user_id = event.from_user.id if event.from_user else None
        if user_id is None:
            return await handler(event, data)

        # Исключения — эти пользователи не проходят проверку
        from config import settings
        if user_id in settings.admin_ids_list:
            return await handler(event, data)

        # Получаем bot из события напрямую (надёжнее чем из data)
        if isinstance(event, Message):
            bot = event.bot
        elif isinstance(event, CallbackQuery):
            bot = event.bot or (event.message.bot if event.message else None)
        else:
            bot = data.get("bot")

        if bot is None:
            logger.warning("SponsorMiddleware: bot is None, skipping check")
            return await handler(event, data)

        subscribed = await _is_subscribed(bot, user_id, sponsor["channel"])
        logger.debug("SponsorMiddleware: uid=%s channel=%s subscribed=%s", user_id, sponsor["channel"], subscribed)

        if subscribed:
            return await handler(event, data)

        # Не подписан — показываем плашку
        await _show_sponsor(event, bot, sponsor["link"])
