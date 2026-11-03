"""Durable callback inbox and ordered retryable delivery, independent of Telegram."""
import asyncio
import hashlib
import json
import logging
import uuid
from datetime import timedelta
from sqlalchemy import select, exists
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError
from bot.models.vk import VKAccount, VKInbox, VKOutbox, utcnow
from bot.services.cache import get_redis

logger = logging.getLogger(__name__)


async def enqueue(session, key, uid, message):
    if await session.scalar(select(VKInbox.id).where(VKInbox.event_key == key)):
        return False
    session.add(VKInbox(event_key=key, vk_id=uid, message=message))
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


def chunks(text, size=3000):
    while text:
        if len(text) <= size:
            yield text
            return
        end = text.rfind("\n", 0, size)
        if end < size//2:
            end = text.rfind(" ", 0, size)
        if end <= 0:
            end = size
        yield text[:end]
        text = text[end:].lstrip("\n ")


class Reply:
    def __init__(self, session, event):
        self.session, self.event, self.index = session, event, 0

    async def send(self, text, keyboard=None, attachment=None, card_key=None):
        parts = list(chunks(text))
        for i, part in enumerate(parts):
            key = f"{self.event.event_key}:{self.index}"
            self.index += 1
            if await self.session.scalar(select(VKOutbox.id).where(VKOutbox.key == key)):
                continue
            body = {"message": part}
            if keyboard and i == len(parts)-1:
                body["keyboard"] = json.dumps(keyboard, ensure_ascii=False)
            if attachment and i == 0:
                body["attachment"] = attachment
            if card_key and i == 0:
                body["_card_key"] = card_key
            self.session.add(VKOutbox(key=key, vk_id=self.event.vk_id, body=body))


async def process_event(maker, api, event_id):
    from bot.vk_menu.controller import handle
    async with maker() as session:
        event = await session.get(VKInbox, event_id)
        if not event or event.status != "pending":
            return
        reply = Reply(session, event)
        await handle(session, maker, api, event, reply)
        event.status = "done"
        await session.commit()


async def worker(maker, api):
    while True:
        try:
            async with maker() as session:
                earlier = aliased(VKInbox)
                rows = (await session.execute(select(VKInbox.id, VKInbox.vk_id).where(
                    VKInbox.status == "pending", VKInbox.available_at <= utcnow(),
                    ~exists(select(earlier.id).where(earlier.vk_id == VKInbox.vk_id, earlier.id < VKInbox.id,
                                                     earlier.status == "pending")))
                    .order_by(VKInbox.id).limit(12))).all()
            worked = False
            for event_id, uid in rows:
                r = await get_redis()
                lock, token = f"vk-menu:lock:{uid}", uuid.uuid4().hex
                if not await r.set(lock, token, nx=True, ex=240):
                    continue
                worked = True
                try:
                    await asyncio.wait_for(process_event(maker, api, event_id), timeout=200)
                except Exception as exc:
                    logger.warning("VK menu event failed: %s", type(exc).__name__)
                    async with maker() as session:
                        event = await session.get(VKInbox, event_id)
                        event.attempts += 1
                        event.available_at = utcnow()+timedelta(seconds=min(120, 2**event.attempts))
                        if event.attempts >= 8:
                            event.status = "failed"
                            await Reply(session, event).send("Не удалось завершить действие. Покупка и готовые разборы сохранены. Откройте «Мои разборы» или «Профиль → Покупки».")
                        await session.commit()
                finally:
                    await r.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0", 1, lock, token)
                break
            if not worked:
                await asyncio.sleep(0.7)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("VK queue unavailable: %s", type(exc).__name__)
            await asyncio.sleep(3)


async def deliver(maker, api, row):
    random_id = int.from_bytes(hashlib.sha256(row.key.encode()).digest()[:4], "big") & 0x7fffffff or 1
    body = {k:v for k,v in row.body.items() if not k.startswith("_")}
    if row.body.get("_card_key"):
        from bot.handlers.tarot import MAJOR_ARCANA, ASSETS_DIR
        key = row.body["_card_key"]
        if key in {c[0] for c in MAJOR_ARCANA}:
            try:
                r = await get_redis()
                attachment = await r.get(f"vk-menu:card-photo:{key}")
                if not attachment and (ASSETS_DIR/f"{key}.png").is_file():
                    from vkbottle import PhotoMessageUploader
                    attachment = await PhotoMessageUploader(api).upload(str(ASSETS_DIR/f"{key}.png"), peer_id=row.vk_id)
                    await r.set(f"vk-menu:card-photo:{key}", str(attachment))
                if attachment:
                    body["attachment"] = str(attachment)
            except Exception as exc:
                logger.warning("VK card image unavailable: %s", type(exc).__name__)
    await api.messages.send(peer_id=row.vk_id, random_id=random_id, **body)


async def sender(maker, api):
    while True:
        try:
            async with maker() as session:
                earlier = aliased(VKOutbox)
                row = await session.scalar(select(VKOutbox).where(VKOutbox.status == "pending",
                    VKOutbox.available_at <= utcnow(), ~exists(select(earlier.id).where(
                        earlier.vk_id == VKOutbox.vk_id, earlier.id < VKOutbox.id, earlier.status == "pending")))
                    .order_by(VKOutbox.id).limit(1))
                if row:
                    try:
                        account = await session.get(VKAccount, row.vk_id)
                        if account and account.manual_support and not row.body.get("_support_notice"):
                            row.status = "suppressed"
                        else:
                            await asyncio.wait_for(deliver(maker, api, row), timeout=30)
                            row.status = "sent"
                    except Exception as exc:
                        logger.warning("VK delivery failed: %s", type(exc).__name__)
                        row.attempts += 1
                        row.available_at = utcnow()+timedelta(seconds=min(600, 2**row.attempts))
                        if row.attempts >= 20:
                            row.status = "failed"
                    await session.commit()
            await asyncio.sleep(0.4 if row else 0.8)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("VK outbox unavailable: %s", type(exc).__name__)
            await asyncio.sleep(3)


def start_workers(maker, api):
    return [asyncio.create_task(worker(maker, api), name=f"vk-menu-{i}") for i in range(4)] + [
        asyncio.create_task(sender(maker, api), name="vk-menu-delivery")]
