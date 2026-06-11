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


_VK_TIERS = {
    "monthly_990": {"price": 990, "name": "Работа со мной — месяц", "days": 30},
    "q29":         {"price": 29,  "name": "Ответ на вопрос"},
}


async def set_payment_offered_at(uid: int) -> None:
    """Сохранить время когда показали оффер (для пушей)."""
    import time
    from bot.services.cache import get_redis
    r = await get_redis()
    await r.set(f"vk:pay_offered:{uid}", str(int(time.time())), ex=86400 * 7)


def create_payment_link(vk_user_id: int, tier_key: str) -> str:
    """Создать платёж в ЮКассе и вернуть ссылку на оплату."""
    from yookassa import Payment
    from bot.business_dialog.upsell import get_tier

    _configure_yookassa()
    tier  = _VK_TIERS.get(tier_key) or get_tier(tier_key)
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

        if tier_key == "monthly_990":
            await _process_vk_monthly(int(vk_user_id), payment_id)
        elif tier_key == "q29":
            await _process_vk_q29(int(vk_user_id), payment_id)
        else:
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


async def _process_vk_q29(vk_user_id: int, payment_id: str) -> None:
    """Ответить на один вопрос за 29 ₽, затем пригласить задать следующий."""
    import json
    import asyncio
    import random
    from datetime import datetime
    from bot.vk_dialog.session_manager import set_stage, get_profile
    from bot.business_dialog.services import generate_business
    from bot.prompts.prompts import PERSONAL_QUESTION_PAID_PROMPT
    from bot.services.numerology import calculate_all

    if not _vk_api:
        logger.error("VK API not initialized in payments.py")
        return

    profile = await get_profile(vk_user_id)

    async def _send_msg(text: str) -> None:
        try:
            await _vk_api.messages.send(
                peer_id=vk_user_id,
                message=text,
                random_id=random.randint(1, 2**31),
            )
        except Exception as e:
            logger.warning("VK q29 send failed for %s: %s", vk_user_id, e)

    async def _typing_sec(seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            try:
                await _vk_api.messages.set_activity(peer_id=vk_user_id, type="typing")
            except Exception:
                pass
            sleep_for = min(5.0, seconds - elapsed)
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for

    def _calc_typing_secs(text: str) -> float:
        chars = len(text)
        total = random.uniform(1.5, 3.0) + chars / 4.0
        return min(total * random.uniform(0.85, 1.15), 22.0)

    await _send_msg("Оплата прошла, душа моя 🌙\n\nСейчас посмотрю ваш вопрос…")

    # Числа судьбы из даты рождения
    birth_date_str = profile.get("birth_date", "")
    nums: dict = {}
    if birth_date_str:
        try:
            bd = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
            nums = calculate_all(bd)
        except Exception:
            pass

    question = profile.get("problem", "")
    context = json.dumps({
        "name":       profile.get("name", ""),
        "birth_date": birth_date_str,
        "question":   question,
        "numbers":    {k: v for k, v in nums.items() if k in ("life_path", "destiny", "personality")},
    }, ensure_ascii=False)

    await _typing_sec(6)
    answer = await generate_business(
        PERSONAL_QUESTION_PAID_PROMPT("ru"),
        f"Ответь на личный вопрос пользователя.\nДанные: {context}",
        complexity="medium",
        max_tokens=600,
    )
    await _typing_sec(_calc_typing_secs(answer))
    await _send_msg(answer)

    # Приглашение задать следующий вопрос
    await asyncio.sleep(2)
    emo = random.choice(["🌙", "✨", "💫", "🔮"])
    await _send_msg(
        f"Если хотите задать ещё вопрос — напишите его, душа моя {emo}\n\n"
        f"Ответ на один вопрос — 29 ₽. Я здесь."
    )
    await set_stage(vk_user_id, "collecting_problem")


async def _process_vk_monthly(vk_user_id: int, payment_id: str) -> None:
    """Активировать ежемесячную подписку VK (monthly_990)."""
    import time
    from bot.vk_dialog.session_manager import set_stage
    from bot.services.cache import get_redis

    r = await get_redis()
    await set_stage(vk_user_id, "paid_monthly")
    await r.set(f"vk:paid_until:{vk_user_id}", str(int(time.time()) + 86400 * 30), ex=86400 * 31)

    if not _vk_api:
        logger.error("VK API not initialized in payments.py")
        return

    import random as _rand
    confirm = "Оплата прошла, душа моя 🌙\n\nТеперь я с вами весь месяц. Задавайте вопросы — я здесь."
    try:
        await _vk_api.messages.send(
            peer_id=vk_user_id,
            message=confirm,
            random_id=_rand.randint(1, 2**31),
        )
        logger.info("VK monthly_990 activated: uid=%s", vk_user_id)
    except Exception as e:
        logger.warning("VK monthly confirm failed for %s: %s", vk_user_id, e)
