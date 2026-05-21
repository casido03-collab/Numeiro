"""Точка входа бота."""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from config import settings
from database.base import create_tables, async_session_maker
from bot.middlewares.user import UserMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.handlers import start, profile, reading, weekly, compatibility, daily, question, dates, payments, admin, share
from bot.handlers import onboarding, content, cabinet, referral, reports
from bot.services.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Numeiro bot...")

    # Создаём таблицы
    await create_tables()

    # Bot и Dispatcher
    # Таймаут сессии: 60 сек — бот не будет висеть при сетевых проблемах
    session = AiohttpSession(timeout=60)
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    # Middleware: сессия БД (регистрируем первой)
    from bot.middlewares.db import DbSessionMiddleware
    dp.update.outer_middleware(DbSessionMiddleware(async_session_maker))
    dp.update.outer_middleware(UserMiddleware())
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    # Роутеры
    dp.include_routers(
        onboarding.router,   # онбординг — первым, до start
        start.router,
        content.router,      # reply-кнопки «🔮 Меню» и «📚 Интересное»
        cabinet.router,      # reply-кнопка «💎 Подписка»
        referral.router,     # reply-кнопка «👥 Друзья»
        reports.router,      # 🌀 Мои Разборы
        profile.router,
        reading.router,
        weekly.router,
        compatibility.router,
        daily.router,
        question.router,
        dates.router,
        payments.router,
        admin.router,
        share.router,
    )

    # Планировщик
    scheduler = setup_scheduler(bot, async_session_maker)
    scheduler.start()

    # Запуск
    try:
        logger.info("Bot started. Press Ctrl+C to stop.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
