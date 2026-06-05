"""
Технический бот @Invest_reinvest_bot — проверяет подписку пользователей на каналы спонсора.

Запускается как отдельный сервис внутри Docker-сети.
Основной бот никогда не добавляется в каналы — только этот бот является администратором.

HTTP API (только внутренняя сеть, порт 8081 не пробрасывается наружу):
    POST /check_subscription
    Headers: X-Secret: <CHECKER_SECRET>
    Body:    {"user_id": 123456789, "channel": "@channel_username_or_-100id"}
    Returns: {"subscribed": true/false}
"""
import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        token = os.environ["CHECKER_BOT_TOKEN"]
        _bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot


async def handle_check(request: web.Request) -> web.Response:
    # Проверяем секрет
    expected = os.environ.get("CHECKER_SECRET", "")
    if not expected or request.headers.get("X-Secret", "") != expected:
        return web.json_response({"error": "forbidden"}, status=403)

    try:
        body = await request.json()
        user_id = int(body["user_id"])
        channel = body["channel"]
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)

    try:
        bot = _get_bot()
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        subscribed = member.status in ("member", "administrator", "creator")
        logger.info("check uid=%s channel=%s → %s", user_id, channel, subscribed)
    except Exception as e:
        logger.warning("get_chat_member failed uid=%s channel=%s: %s", user_id, channel, e)
        # fail-open: при ошибке не блокируем пользователя
        subscribed = True

    return web.json_response({"subscribed": subscribed})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True})


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    token = os.environ.get("CHECKER_BOT_TOKEN", "")
    if not token:
        logger.error("CHECKER_BOT_TOKEN не задан — завершение.")
        return

    app = web.Application()
    app.router.add_post("/check_subscription", handle_check)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", 8081).start()
    logger.info("Checker bot started on port 8081")

    # Держим процесс живым
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
