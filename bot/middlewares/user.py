"""Middleware: ensure user exists in DB on every update."""
import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TGUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from bot.models.user import User, Subscription, UserProfile, PlanEnum
import secrets
import string

logger = logging.getLogger(__name__)


def _generate_referral_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TGUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        session: AsyncSession = data["session"]

        result = await session.execute(
            select(User).where(User.telegram_id == tg_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.info("USER_MW: new user telegram_id=%s", tg_user.id)
            try:
                user = User(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    referral_code=_generate_referral_code(),
                )
                session.add(user)
                # flush даёт user.id без полного commit
                await session.flush()
                logger.info("USER_MW: user flushed, id=%s", user.id)

                profile = UserProfile(user_id=user.id)
                subscription = Subscription(user_id=user.id, plan=PlanEnum.free)
                session.add(profile)
                session.add(subscription)
                await session.commit()
                # expire_on_commit=False — refresh НЕ нужен, объект уже актуален
                logger.info("USER_MW: new user committed, id=%s", user.id)
            except IntegrityError:
                # Гонка: другой запрос уже создал пользователя — просто загрузим его
                await session.rollback()
                logger.warning("USER_MW: race condition for telegram_id=%s — re-fetching", tg_user.id)
                result = await session.execute(
                    select(User).where(User.telegram_id == tg_user.id)
                )
                user = result.scalar_one()
        else:
            if user.first_name != tg_user.first_name or user.username != tg_user.username:
                user.first_name = tg_user.first_name
                user.username = tg_user.username
                await session.commit()

        data["user"] = user

        # ── Загружаем язык пользователя ──────────────────────────────────────
        try:
            from bot.services.cache import get_redis
            redis = await get_redis()
            lang_key = f"user:lang:{tg_user.id}"
            cached = await redis.get(lang_key)
            if cached:
                data["lang"] = cached.decode() if isinstance(cached, bytes) else cached
            else:
                # Загружаем из БД и кэшируем
                pr = await session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                profile = pr.scalar_one_or_none()
                lang = "ru"
                if profile and profile.preferences:
                    stored = profile.preferences.get("lang")
                    if stored:
                        lang = stored
                        # Кэшируем только если явно выбран язык
                        await redis.set(lang_key, lang, ex=86400 * 30)
                data["lang"] = lang
        except Exception as e:
            logger.warning("USER_MW: failed to load lang for %s: %s", tg_user.id, e)
            data["lang"] = "ru"

        logger.info("USER_MW: USER LOADED OR CREATED id=%s lang=%s", user.id, data.get("lang", "ru"))
        return await handler(event, data)
