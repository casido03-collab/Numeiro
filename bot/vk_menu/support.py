"""Operator mode applies to scheduled and legacy replies too."""
from sqlalchemy import select
from database.base import async_session_maker
from bot.models.vk import VKAccount


async def is_manual_support(uid):
    async with async_session_maker() as session:
        return bool(await session.scalar(select(VKAccount.manual_support).where(VKAccount.vk_id==uid)))


class SupportAwareMessages:
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        return getattr(self.original, name)

    async def send(self, peer_id=None, **kwargs):
        if peer_id and await is_manual_support(peer_id):
            return 0
        return await self.original.send(peer_id=peer_id, **kwargs)


class SupportAwareAPI:
    def __init__(self, api):
        self.api = api
        self.messages = SupportAwareMessages(api.messages)

    def __getattr__(self, name):
        return getattr(self.api, name)
