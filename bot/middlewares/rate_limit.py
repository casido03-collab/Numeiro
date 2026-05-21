"""Rate limiting middleware."""
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from bot.services.cache import rate_limit_check, set_user_processing, get_cooldown_remaining
from config import RATE_LIMITS


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from aiogram.types import User as TGUser
        tg_user: TGUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        uid = tg_user.id

        # Проверка кнопок
        if isinstance(event, CallbackQuery):
            ok = await rate_limit_check(uid, "buttons", RATE_LIMITS["buttons_per_5sec"], 5)
            if not ok:
                await event.answer("✨ Подождите немного...", show_alert=False)
                return

        # Проверка AI-запросов для сообщений
        if isinstance(event, Message):
            # Команды (/start, /help, ...) и reply-кнопки навигации не ограничиваем —
            # они не генерируют AI-запросы и должны работать всегда.
            _EXEMPT_TEXTS = {"🔮 Меню", "📚 Интересное", "👥 Друзья", "💎 Подписка"}
            if event.text and (
                event.text.startswith("/") or event.text in _EXEMPT_TEXTS
            ):
                return await handler(event, data)

            ok_10 = await rate_limit_check(uid, "ai_10s", RATE_LIMITS["ai_per_10sec"], 10)
            ok_min = await rate_limit_check(uid, "ai_min", RATE_LIMITS["ai_per_minute"], 60)

            if not ok_10 or not ok_min:
                await event.answer(
                    "✨ Энергетический поток перегружен. Подождите немного перед следующим запросом."
                )
                return

        return await handler(event, data)
