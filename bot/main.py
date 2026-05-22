"""Точка входа бота."""
import asyncio
import logging
import os
import signal
import time
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot.services.resilient_session import ResilientSession
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

# ─── Watchdog: timestamp последнего обработанного апдейта ─────────────────────
# Пишется в файл чтобы Docker healthcheck мог его прочитать
_HEALTH_FILE = "/tmp/bot_last_update"
_WATCHDOG_TIMEOUT = 600  # 10 минут без апдейтов → считаем зависшим


def touch_health():
    """Обновить timestamp — вызывается на каждый обработанный апдейт."""
    try:
        with open(_HEALTH_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def check_health() -> bool:
    """Вернуть True если бот живой (апдейт был недавно или бот только стартовал)."""
    try:
        with open(_HEALTH_FILE) as f:
            last = float(f.read().strip())
        return (time.time() - last) < _WATCHDOG_TIMEOUT
    except Exception:
        return True  # файл ещё не создан — значит только стартовали


async def main():
    logger.info("Starting Numeiro bot...")
    touch_health()  # сброс watchdog при старте

    # Создаём таблицы
    await create_tables()

    # Bot и Dispatcher
    # Настраиваем TCP-коннектор против зомби-соединений после простоя.
    #
    # keepalive_timeout=5: соединение, пролежавшее в пуле >5 сек, выбрасывается.
    # После любого перерыва в общении (>5с) пул будет пустым → следующий запрос
    # создаст свежий TCP и не зависнет на зомби-соединении.
    #
    # timeout=15: дефолтный таймаут всех Telegram API-вызовов снижен с 60с до 15с.
    # int(15) + polling_timeout(25) = 40с — допустимо для polling.
    # Без этого message.answer() после зомби-delete мог ждать 60с.
    _session = ResilientSession(timeout=8)
    _session._connector_init["enable_cleanup_closed"] = True
    _session._connector_init["keepalive_timeout"] = 5

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        session=_session,
    )

    storage = RedisStorage.from_url(
        settings.redis_url,
        connection_kwargs={
            "socket_timeout": 5,
            "socket_connect_timeout": 5,
            "retry_on_timeout": True,
            "health_check_interval": 30,
        },
    )
    dp = Dispatcher(storage=storage)

    # Middleware: сессия БД (регистрируем первой)
    from bot.middlewares.db import DbSessionMiddleware
    from bot.middlewares.activity import ActivityMiddleware

    dp.update.outer_middleware(DbSessionMiddleware(async_session_maker))
    dp.update.outer_middleware(UserMiddleware())
    # Activity tracking — после UserMiddleware (нужен user в data)
    dp.message.outer_middleware(ActivityMiddleware(async_session_maker))
    dp.callback_query.outer_middleware(ActivityMiddleware(async_session_maker))
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    # Обновляем healthcheck-файл на каждый обработанный апдейт
    @dp.update.outer_middleware()
    async def health_touch_middleware(handler, event, data):
        result = await handler(event, data)
        touch_health()
        return result

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

    # Watchdog: каждые 5 мин проверяет не завис ли polling
    async def _watchdog():
        await asyncio.sleep(300)  # первые 5 мин — grace period
        while True:
            await asyncio.sleep(300)
            if not check_health():
                logger.error("WATCHDOG: no updates for %s sec — restarting", _WATCHDOG_TIMEOUT)
                os.kill(os.getpid(), signal.SIGTERM)
                break

    asyncio.create_task(_watchdog())

    # Гарантированно сбросить webhook перед polling (на случай если был зарегистрирован)
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook cleared, starting polling...")

    # Запуск
    try:
        logger.info("Bot started. Press Ctrl+C to stop.")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            polling_timeout=25,     # Telegram держит long-poll 25 сек
            handle_signals=True,    # корректно обрабатывать SIGTERM
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
