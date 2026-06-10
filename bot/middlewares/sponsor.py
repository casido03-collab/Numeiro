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

# Reply-кнопки нижнего меню которые требуют проверки (все языки)
from bot.keyboards.reply import ALL_REPLY_TEXTS as _GATED_REPLIES


async def _get_sponsor_state() -> dict:
    try:
        from bot.handlers.sponsor import get_sponsor_state
        return await get_sponsor_state()
    except Exception as e:
        logger.warning("SponsorMiddleware: get_sponsor_state failed: %s", e)
        return {"enabled": False, "link": "", "channel": ""}


async def _is_subscribed(bot, user_id: int, channel: str) -> bool:
    """Проверить подписку через бота-чекера (HTTP).
    Если чекер недоступен — пропускаем пользователя (fail-open).
    """
    from config import settings
    import aiohttp

    checker_url = settings.checker_url
    checker_secret = settings.checker_secret

    if checker_url and checker_secret:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{checker_url}/check_subscription",
                    json={"user_id": user_id, "channel": channel},
                    headers={"X-Secret": checker_secret},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("subscribed", True)
                    logger.warning(
                        "Checker returned HTTP %s for uid=%s", resp.status, user_id
                    )
        except Exception as e:
            logger.warning("Checker service unavailable for uid=%s: %s", user_id, e)
        # fail-open: чекер недоступен — не блокируем пользователя
        return True

    # Fallback: прямая проверка основным ботом (только если чекер не настроен)
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning("Direct sponsor check error for uid=%s: %s", user_id, e)
        return True


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
