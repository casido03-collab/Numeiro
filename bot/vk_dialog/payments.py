"""ЮКасса — создание платёжных ссылок и обработка webhook для VK-диалога."""
import logging
import uuid

from aiohttp import web

logger = logging.getLogger(__name__)

# Глобальный VK API — инициализируется из router.py
_vk_api = None


def setup_vk_payments(vk_api) -> None:
    global _vk_api
    _vk_api = vk_api


def _configure_yookassa():
    from config import settings
    from yookassa import Configuration
    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key


def create_payment_link(vk_user_id: int, tier_key: str) -> str:
    """Создать платёж в ЮКассе и вернуть ссылку на оплату."""
    from yookassa import Payment
    from bot.business_dialog.upsell import get_tier

    _configure_yookassa()
    tier  = get_tier(tier_key)
    price = tier.get("price", 190)
    name  = tier.get("name", "Консультация")

    payment = Payment.create({
        "amount":        {"value": f"{price}.00", "currency": "RUB"},
        "confirmation":  {"type": "redirect", "return_url": "https://vk.com/babushkaaisha"},
        "capture":       True,
        "description":   f"Аиша — {name}",
        "metadata": {
            "platform":    "vk",
            "vk_user_id":  str(vk_user_id),
            "tier_key":    tier_key,
        },
    }, str(uuid.uuid4()))

    return payment.confirmation.confirmation_url


# ─── Webhook handler ──────────────────────────────────────────────────────────

async def handle_vk_payment_webhook(
    request: web.Request,
    _parsed: tuple | None = None,
) -> web.Response:
    """Обработка VK-платежа ЮКассы.

    Вызывается двумя способами:
    - Напрямую (старый маршрут /yookassa/vk_webhook) — читаем тело сами
    - Из единого обработчика /yookassa/webhook — получаем уже распарсенные данные через _parsed
    """
    import json
    try:
        if _parsed is not None:
            # Данные уже распарсены основным обработчиком
            data, payment_obj, metadata = _parsed
        else:
            body = await request.text()
            data = json.loads(body)

            if data.get("event") != "payment.succeeded":
                return web.Response(status=200)

            payment_obj = data.get("object", {})
            if payment_obj.get("status") != "succeeded":
                return web.Response(status=200)

            metadata = payment_obj.get("metadata", {})
            if metadata.get("platform") != "vk":
                return web.Response(status=200)

        logger.info("VK YooKassa webhook: processing payment")

        payment_id = payment_obj.get("id")
        vk_user_id = metadata.get("vk_user_id")
        tier_key   = metadata.get("tier_key")
        amount     = float(payment_obj.get("amount", {}).get("value", 0))

        if not vk_user_id or not tier_key:
            logger.error("VK webhook: missing metadata in payment %s", payment_id)
            return web.Response(status=200)

        # Дедупликация
        from bot.services.cache import get_redis
        r = await get_redis()
        already = not await r.set(f"vk_paid:{payment_id}", "1", nx=True, ex=86400)
        if already:
            logger.info("VK payment %s already processed", payment_id)
            return web.Response(status=200)

        await _process_vk_payment(int(vk_user_id), tier_key, payment_id, int(amount))

    except Exception:
        logger.exception("VK YooKassa webhook error")

    return web.Response(status=200)


async def _process_vk_payment(vk_user_id: int, tier_key: str, payment_id: str, amount: int) -> None:
    """Активировать консультацию после оплаты через VK."""
    from bot.vk_dialog.session_manager import (
        set_stage, set_paid_tier, set_followup_left, get_profile, store_field,
        get_tier_msg_count,
    )
    from bot.business_dialog.upsell import get_tier, is_accompaniment
    from bot.business_dialog.services import generate_business
    from bot.business_dialog.prompts import (
        AISHA_PAID_PROMPT, AISHA_CAUSE_PROMPT,
        AISHA_ACCOMPANIMENT_PROMPT, AISHA_TAROT_BUSINESS_PROMPT,
    )
    from bot.business_dialog.utils import followup_invite
    import json
    import asyncio
    import random

    tier           = get_tier(tier_key)
    followup_limit = tier.get("followup_limit") or 2

    await set_paid_tier(vk_user_id, tier_key)
    await set_followup_left(vk_user_id, followup_limit)

    if not _vk_api:
        logger.error("VK API not initialized in payments.py")
        return

    async def _send(text: str) -> None:
        try:
            await _vk_api.messages.send(
                peer_id=vk_user_id,
                message=text,
                random_id=random.randint(1, 2**31),
            )
        except Exception as e:
            logger.warning("VK send failed for %s: %s", vk_user_id, e)

    async def _typing(seconds: float = 2.0) -> None:
        """Держать индикатор «печатает» ровно seconds секунд (обновляем каждые 5 сек)."""
        elapsed = 0.0
        while elapsed < seconds:
            try:
                await _vk_api.messages.set_activity(peer_id=vk_user_id, type="typing")
            except Exception:
                pass
            sleep_for = min(5.0, seconds - elapsed)
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for

    def _calc_typing(text: str) -> float:
        """Рассчитать реалистичную задержку по длине текста (макс 22 сек)."""
        import random as _rnd
        chars = len(text)
        total = _rnd.uniform(1.5, 3.0) + chars / 4.0
        return min(total * _rnd.uniform(0.85, 1.15), 22.0)

    # Подтверждение
    confirm_msgs = {
        "t190":  "Оплата прошла, душа моя 🌙\n\nСейчас я спокойно посмотрю вашу ситуацию…",
        "t490":  "Получила, душа моя ✨\n\nСейчас буду смотреть причину — глубоко и внимательно…",
        "t990":  "Оплата прошла 💫\n\nЗадайте мне один вопрос — самый важный для вас сейчас 🔮\n\nНапишите его — я жду.",
        "t1990": "Я рядом, душа моя 🌟\n\nКаждое утро в 8 часов буду присылать вам план на день.\nПишите мне — до 6 вопросов в день. Я здесь 🌙",
        "t4990": "Оплата прошла 🔮\n\nНачинаю наблюдение — буду рядом…",
        "t9900": "Получила, душа моя 💎\n\nЭто особенный просмотр — приступаю…",
    }
    await _send(confirm_msgs.get(tier_key, "Оплата прошла 🌙\n\nСейчас посмотрю вашу ситуацию…"))

    # t990 — ждём вопроса от клиента
    if tier_key == "t990":
        await set_stage(vk_user_id, "t990_waiting_question")
        return

    # Сопровождение — сразу переводим в accompaniment
    if is_accompaniment(tier_key):
        await set_stage(vk_user_id, "accompaniment")
        return

    # Остальные тиры — генерируем разбор
    _TIER_PROMPTS = {
        "t190": (AISHA_PAID_PROMPT,  "complex", 900),
        "t490": (AISHA_CAUSE_PROMPT, "complex", 900),
    }
    prompt, complexity, max_tokens = _TIER_PROMPTS.get(tier_key, (AISHA_PAID_PROMPT, "complex", 900))

    profile = await get_profile(vk_user_id)
    context = json.dumps(profile, ensure_ascii=False)

    await _typing(6)  # пауза перед генерацией — имитируем обдумывание
    consultation = await generate_business(
        prompt,
        f"Данные клиента: {context}",
        complexity=complexity,
        max_tokens=max_tokens,
    )
    # Typing по длине текста перед отправкой разбора
    await _typing(_calc_typing(consultation))
    await _send(consultation)

    await _typing(3)
    await _send(followup_invite(followup_limit))
    await set_stage(vk_user_id, "followup")
