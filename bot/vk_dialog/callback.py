"""VK Callback API — вебхук для входящих сообщений ВКонтакте.

Надёжнее Long Poll: VK сам шлёт события и повторяет при недоступности сервера.
"""
import json
import logging

from aiohttp import web

from config import settings
from bot.vk_dialog.handlers import handle_vk_message

logger = logging.getLogger(__name__)

_vk_api = None  # устанавливается из router.py


def setup_vk_callback(api, app: web.Application) -> None:
    """Зарегистрировать маршрут /vk/callback в aiohttp-приложении."""
    global _vk_api
    _vk_api = api
    app.router.add_post("/vk/callback", handle_vk_callback)
    logger.info("VK Callback API endpoint registered at /vk/callback")


async def handle_vk_callback(request: web.Request) -> web.Response:
    """Обработчик POST /vk/callback от ВКонтакте."""
    try:
        body = await request.text()
        data = json.loads(body)
    except Exception as e:
        logger.warning("VK callback: bad JSON — %s", e)
        return web.Response(text="ok")

    event_type = data.get("type")

    # 1. Подтверждение адреса сервера
    if event_type == "confirmation":
        confirm = settings.vk_callback_confirm
        if not confirm:
            logger.error("VK_CALLBACK_CONFIRM not set in .env")
            return web.Response(text="ok")
        logger.info("VK callback: confirmation request answered")
        return web.Response(text=confirm)

    # 2. Проверка секретного ключа
    secret = settings.vk_callback_secret
    if secret and data.get("secret") != secret:
        logger.warning("VK callback: invalid secret")
        return web.Response(text="ok")

    # 3. Входящее сообщение — отвечаем VK НЕМЕДЛЕННО, обрабатываем в фоне
    if event_type == "message_new":
        msg = data.get("object", {}).get("message", {})
        uid  = msg.get("from_id")
        text = msg.get("text", "")

        if uid and text and _vk_api is not None:
            import asyncio

            async def _process():
                first_name = ""
                try:
                    users = await _vk_api.users.get(user_ids=[uid])
                    if users:
                        first_name = users[0].first_name or ""
                except Exception:
                    pass
                try:
                    await handle_vk_message(
                        api=_vk_api,
                        uid=uid,
                        text=text,
                        first_name=first_name,
                    )
                except Exception:
                    logger.exception("VK callback handler error (uid=%s)", uid)

            asyncio.create_task(_process())

    # Отвечаем VK сразу — иначе VK повторит событие через ~10 сек
    return web.Response(text="ok")
