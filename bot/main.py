"""Точка входа бота."""
import asyncio
import logging
import os
import signal
import threading
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from bot.services.resilient_session import ResilientSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from bot.services.runtime_health import (
    RuntimeHealth, heartbeat_loop, dependency_loop, start_watchdog,
    internal_health_response,
)

from config import settings
from database.base import create_tables, async_session_maker
from bot.middlewares.user import UserMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware
from bot.handlers import start, profile, reading, weekly, compatibility, daily, question, dates, payments, admin, share
from bot.handlers import onboarding, content, cabinet, referral, reports, tarot, horoscope
from bot.handlers import lang_select
from bot.handlers import sponsor as sponsor_handler
from bot.services.scheduler import setup_scheduler
from bot.handlers.yookassa_webhook import setup_webhook, handle_yookassa_webhook
from bot.business_dialog.router import router as business_router, setup_business_dialog
import bot.business_dialog.models  # регистрируем business_ таблицы в Base.metadata
from bot.vk_dialog.router import create_vk_bot, run_vk_polling

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Numeiro bot...")
    health = RuntimeHealth()
    scheduler = None
    polling_running = False

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
    from bot.middlewares.service_errors import ServiceErrorsMiddleware
    dp.message.outer_middleware(ServiceErrorsMiddleware())
    dp.callback_query.outer_middleware(ServiceErrorsMiddleware())
    dp.business_message.outer_middleware(ServiceErrorsMiddleware())
    # Activity tracking — после UserMiddleware (нужен user в data)
    dp.message.outer_middleware(ActivityMiddleware(async_session_maker))
    dp.callback_query.outer_middleware(ActivityMiddleware(async_session_maker))
    dp.message.outer_middleware(RateLimitMiddleware())
    dp.callback_query.outer_middleware(RateLimitMiddleware())

    # Спонсорская проверка подписки
    from bot.middlewares.sponsor import SponsorMiddleware
    _sponsor_mw = SponsorMiddleware()
    dp.message.outer_middleware(_sponsor_mw)
    dp.callback_query.outer_middleware(_sponsor_mw)

    # Incoming activity is diagnostic only, never a liveness signal.
    @dp.update.outer_middleware()
    async def incoming_activity_middleware(handler, event, data):
        health.incoming()
        return await handler(event, data)

    # Роутеры
    dp.include_routers(
        business_router,          # business_dialog — первым, отдельный update type
        sponsor_handler.router,   # спонсор — вторым, перехватывает sponsor:check
        lang_select.router,       # выбор языка — до онбординга
        onboarding.router,        # онбординг — первым, до start
        start.router,
        content.router,      # reply-кнопки «🔮 Меню» и «📚 Интересное»
        cabinet.router,      # reply-кнопка «💎 Подписка»
        referral.router,     # reply-кнопка «👥 Друзья»
        reports.router,      # 🌀 Мои Разборы
        horoscope.router,    # 🔯 Гороскоп
        tarot.router,        # 🃏 Карта дня
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

    # VK бот создаём ДО старта сервера — чтобы зарегистрировать маршрут /vk/callback
    from bot.vk_dialog.callback import setup_vk_callback
    _vk_bot = create_vk_bot()

    # Webhook-сервер (aiohttp на порту 8080) — YooKassa + Tribute + VK
    from aiohttp import web as aiohttp_web
    setup_webhook(bot, async_session_maker)
    _webhook_app = aiohttp_web.Application()

    async def runtime_health_response(request):
        return await internal_health_response(
            request, health, scheduler is not None and scheduler.running, polling_running,
        )

    # Единый webhook ЮКассы — маршрутизирует по metadata.platform (tg / vk)
    _webhook_app.router.add_post("/yookassa/webhook", handle_yookassa_webhook)
    # Business dialog: Tribute webhook + инициализация модуля
    setup_business_dialog(bot, async_session_maker, _webhook_app)
    # VK Callback API — регистрируем ДО запуска сервера
    if _vk_bot:
        setup_vk_callback(_vk_bot.api, _webhook_app)
    _webhook_runner = aiohttp_web.AppRunner(_webhook_app)
    await _webhook_runner.setup()
    await aiohttp_web.TCPSite(_webhook_runner, "0.0.0.0", 8080).start()
    logger.info("Webhook server started on port 8080 (YooKassa + Tribute + VK)")

    if _vk_bot:
        logger.info("VK Callback API ready at /vk/callback")
    from bot.vk_menu.queue import start_workers
    vk_tasks = start_workers(async_session_maker, _vk_bot.api) if _vk_bot else []

    # Планировщик
    scheduler = setup_scheduler(bot, async_session_maker)
    scheduler.start()

    # Separate loopback-only listener, not exposed through public webhook/proxy.
    _health_app = aiohttp_web.Application()
    _health_app.router.add_get("/_internal/health", runtime_health_response)
    _health_runner = aiohttp_web.AppRunner(_health_app)
    await _health_runner.setup()
    await aiohttp_web.TCPSite(_health_runner, "127.0.0.1", 8081).start()

    async def postgres_probe():
        from sqlalchemy import text
        async with async_session_maker() as session:
            return (await session.execute(text("SELECT 1"))).scalar_one() == 1

    async def redis_probe():
        return bool(await storage.redis.ping())

    # Гарантированно сбросить webhook перед polling (на случай если был зарегистрирован)
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Webhook cleared, starting polling...")

    # Main-loop progress, cached dependencies and an independent stall watchdog.
    health_tasks = [
        asyncio.create_task(heartbeat_loop(health), name="service-heartbeat"),
        asyncio.create_task(dependency_loop(health, postgres_probe, redis_probe), name="health-dependencies"),
    ]
    watchdog_stop = threading.Event()

    def runtime_stalled():
        logger.error("WATCHDOG: internal runtime heartbeat stale; SIGTERM requested")
        os.kill(os.getpid(), signal.SIGTERM)

    watchdog_thread = start_watchdog(health, watchdog_stop, runtime_stalled)
    polling_running = True
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
        polling_running = False
        watchdog_stop.set()
        for task in health_tasks:
            task.cancel()
        for task in vk_tasks:
            task.cancel()
        await asyncio.gather(*vk_tasks, return_exceptions=True)
        await asyncio.gather(*health_tasks, return_exceptions=True)
        watchdog_thread.join(timeout=1)
        scheduler.shutdown()
        await _health_runner.cleanup()
        await _webhook_runner.cleanup()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
