"""Точка подключения business_dialog модуля."""
from aiogram import Router
from aiogram import Bot

from bot.business_dialog.handlers import router as _handlers_router, _set_session_maker
from bot.business_dialog.tribute_flow import setup_tribute, handle_tribute_webhook

# Публичный роутер — подключается в main.py
router = Router(name="business_dialog")
router.include_router(_handlers_router)


def setup_business_dialog(bot: Bot, session_maker, aiohttp_app) -> None:
    """
    Инициализация модуля:
    - передаёт bot и session_maker в tribute_flow и handlers
    - регистрирует tribute webhook в aiohttp приложении
    """
    setup_tribute(bot, session_maker)
    _set_session_maker(session_maker)

    # Регистрируем webhook endpoint
    aiohttp_app.router.add_post("/webhooks/tribute", handle_tribute_webhook)
