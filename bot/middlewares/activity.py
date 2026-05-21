"""Middleware: обновляет last_activity_at пользователя на каждый апдейт.

Работает в фоне через asyncio.create_task — не добавляет задержку к хендлерам.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


class ActivityMiddleware(BaseMiddleware):
    def __init__(self, session_maker):
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is not None:
            # Фоновая задача — не блокирует обработку события
            asyncio.create_task(self._track(user.id))
        return await handler(event, data)

    async def _track(self, user_id: int) -> None:
        try:
            from bot.models.user import UserActivity
            async with self.session_maker() as session:
                now = datetime.now(timezone.utc)
                stmt = pg_insert(UserActivity).values(
                    user_id=user_id,
                    last_activity_at=now,
                    updated_at=now,
                ).on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "last_activity_at": now,
                        "updated_at": now,
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            logger.exception("ActivityMiddleware: failed to track user_id=%s", user_id)
