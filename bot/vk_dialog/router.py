"""VK Long Poll — точка входа для бота бабушки Аиши в ВКонтакте."""
import logging

from config import settings
from bot.vk_dialog.handlers import handle_vk_message
from bot.vk_dialog.payments import setup_vk_payments

logger = logging.getLogger(__name__)

_vk_bot = None  # глобальный экземпляр VKBot


def create_vk_bot():
    """Создать и настроить VK-бота. Возвращает None если VK_TOKEN не задан."""
    if not settings.vk_token:
        logger.warning("VK_TOKEN not set — VK bot disabled")
        return None

    from vkbottle.bot import Bot as VKBot, Message

    bot = VKBot(token=settings.vk_token)

    # Передаём VK API в payments.py
    setup_vk_payments(bot.api)

    @bot.on.message()
    async def handle(message: Message) -> None:
        try:
            # Получаем имя пользователя из объекта сообщения, если есть
            first_name = ""
            if hasattr(message, "from_id") and message.from_id:
                try:
                    users = await bot.api.users.get(user_ids=[message.from_id])
                    if users:
                        first_name = users[0].first_name or ""
                except Exception:
                    pass  # имя не критично

            await handle_vk_message(
                api=bot.api,
                uid=message.from_id,
                text=message.text or "",
                first_name=first_name,
            )
        except Exception:
            logger.exception("VK message handler error (uid=%s)", getattr(message, "from_id", "?"))

    logger.info("VK bot created (Long Poll)")
    return bot


async def run_vk_polling(bot) -> None:
    """Запустить Long Poll. Запускается как фоновый asyncio.Task."""
    if bot is None:
        return
    logger.info("VK Long Poll starting…")
    try:
        await bot.run_polling()
    except Exception:
        logger.exception("VK Long Poll crashed")
