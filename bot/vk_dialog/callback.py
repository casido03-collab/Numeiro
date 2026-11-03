"""Authenticate VK callbacks and acknowledge only after durable storage."""
import hmac
import logging
from aiohttp import web
from sqlalchemy import update
from config import settings
from database.base import async_session_maker
from bot.models.vk import VKAccount, VKOutbox
from bot.vk_menu.queue import enqueue
from bot.vk_menu.controller import command

logger = logging.getLogger(__name__)
_vk_api = None


def setup_vk_callback(api, app):
    global _vk_api
    _vk_api = api
    app.router.add_post("/vk/callback", handle_vk_callback)


async def handle_vk_callback(request):
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)
    if not isinstance(data, dict) or data.get("group_id") != settings.vk_group_id:
        return web.Response(status=403)
    if not settings.vk_callback_secret or not hmac.compare_digest(str(data.get("secret", "")), settings.vk_callback_secret):
        return web.Response(status=403)
    if data.get("type") == "confirmation":
        return web.Response(text=settings.vk_callback_confirm) if settings.vk_callback_confirm else web.Response(status=503)
    if data.get("type") not in ("message_new", "message_reply"):
        return web.Response(text="ok")
    if _vk_api is None:
        return web.Response(status=503)
    obj = data.get("object", {})
    msg = obj.get("message", obj)
    uid = msg.get("from_id")
    peer = msg.get("peer_id")
    if data["type"] == "message_reply":
        # Manual community replies pause automation too; bot sends have random_id.
        if isinstance(peer, int) and 0 < peer < 2_000_000_000 and msg.get("admin_author_id") and not msg.get("random_id"):
            try:
                async with async_session_maker() as session:
                    await session.execute(update(VKAccount).where(VKAccount.vk_id==peer).values(manual_support=True))
                    await session.execute(update(VKOutbox).where(VKOutbox.vk_id==peer, VKOutbox.status=="pending").values(status="suppressed"))
                    await session.commit()
            except Exception:
                return web.Response(status=503)
        return web.Response(text="ok")
    if not isinstance(uid,int) or uid<=0 or peer != uid or msg.get("out"):
        return web.Response(text="ok")
    message_id = msg.get("conversation_message_id") or msg.get("id")
    if not message_id:
        return web.Response(status=400)
    key = f"vk:{settings.vk_group_id}:{uid}:{message_id}"
    message = {k:msg[k] for k in ("text", "payload", "ref", "conversation_message_id", "id") if k in msg}
    if len(message.get("text", "")) > 6000:
        message["text"] = message["text"][:6000]
    try:
        async with async_session_maker() as session:
            if command(message) == "support":
                await session.execute(update(VKAccount).where(VKAccount.vk_id==uid).values(manual_support=True))
                await session.execute(update(VKOutbox).where(VKOutbox.vk_id==uid, VKOutbox.status=="pending").values(status="suppressed"))
            await enqueue(session, key, uid, message)
    except Exception as exc:
        logger.warning("VK callback storage failed: %s", type(exc).__name__)
        return web.Response(status=503)
    return web.Response(text="ok")
