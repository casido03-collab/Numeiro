"""Notification preferences shared by scheduled messages and chat commands."""
from bot.services.cache import get_redis


async def muted(platform, user_id):
    return bool(await (await get_redis()).exists(f"notifications:off:{platform}:{user_id}"))


async def set_muted(platform, user_id, value):
    r = await get_redis()
    key = f"notifications:off:{platform}:{user_id}"
    if value:
        await r.set(key, "1")
    else:
        await r.delete(key)


class NotificationBot:
    """Only used by the scheduler; replies and payment receipts are unaffected."""
    def __init__(self, bot):
        self.bot = bot

    def __getattr__(self, name):
        return getattr(self.bot, name)

    async def send_message(self, chat_id=None, text=None, **kwargs):
        if not await muted("tg", chat_id):
            return await self.bot.send_message(chat_id=chat_id, text=text, **kwargs)
