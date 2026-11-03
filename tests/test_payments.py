import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from bot.models.user import Payment
from bot.services.yookassa_service import validate_payment


def paid(**overrides):
    value = {"id":"verified-id","status":"succeeded","paid":True,
             "amount":{"value":"29.00","currency":"RUB"},
             "metadata":{"user_id":"1001","product_type":"product","product_key":"personal_question"}}
    value.update(overrides)
    return value


def test_payment_validation():
    assert validate_payment(paid())
    assert not validate_payment(paid(paid=False))
    assert not validate_payment(paid(status="pending"))
    assert not validate_payment(paid(amount={"value":"1.00","currency":"RUB"}))
    assert not validate_payment(paid(amount={"value":"29.00","currency":"USD"}))
    assert not validate_payment(paid(metadata={"product_type":"product","product_key":"invalid"}))
    assert validate_payment(paid(metadata={"platform":"vk","vk_user_id":"1","tier_key":"q29"}))


async def test_payment_redelivery_grants_once(db, redis, monkeypatch):
    from bot.handlers import yookassa_webhook as webhook
    monkeypatch.setattr(webhook,"_session_maker",db)
    monkeypatch.setattr(webhook,"_bot",NS(send_message=AsyncMock()))
    await webhook._process_payment(1001,"product","personal_question",29.0,"payment-1")
    await webhook._process_payment(1001,"product","personal_question",29.0,"payment-1")
    async with db() as s:
        assert await s.scalar(select(func.count()).select_from(Payment)) == 1
    assert await redis.get("oneoff:personal_question:1") == "1"


async def test_webhook_uses_verified_metadata_not_incoming_body(monkeypatch):
    from bot.handlers import yookassa_webhook as webhook
    from bot.services import yookassa_service
    monkeypatch.setattr(yookassa_service,"verified_payment",AsyncMock(return_value=paid()))
    process = AsyncMock()
    monkeypatch.setattr(webhook,"_process_payment",process)
    request = NS(text=AsyncMock(return_value=json.dumps({"event":"payment.succeeded", "object":
        paid(metadata={"user_id":"9999","product_type":"product","product_key":"vip"})})))
    response = await webhook.handle_yookassa_webhook(request)
    assert response.status == 200
    assert process.call_args.kwargs["telegram_id"] == 1001
    assert process.call_args.kwargs["product_key"] == "personal_question"


async def test_webhook_requests_retry_on_storage_failure(monkeypatch):
    from bot.handlers import yookassa_webhook as webhook
    from bot.services import yookassa_service
    monkeypatch.setattr(yookassa_service,"verified_payment",AsyncMock(return_value=paid()))
    monkeypatch.setattr(webhook,"_process_payment",AsyncMock(side_effect=RuntimeError("database unavailable")))
    request = NS(text=AsyncMock(return_value=json.dumps({"event":"payment.succeeded","object":paid()})))
    assert (await webhook.handle_yookassa_webhook(request)).status == 503


async def test_legacy_guard_failure_is_retryable(redis):
    from bot.services.payment_guard import payment_guard
    with pytest.raises(RuntimeError):
        async with payment_guard("vk_paid","payment") as process:
            assert process
            raise RuntimeError("AI unavailable")
    assert not await redis.exists("vk_paid:payment")
    async with payment_guard("vk_paid","payment") as process:
        assert process
    async with payment_guard("vk_paid","payment") as process:
        assert not process


async def test_legacy_subscription_extends_and_retry_is_free(redis):
    from bot.services.payment_guard import extend_dialogue_subscription
    first = int(await extend_dialogue_subscription("vk",1,"p1"))
    second = int(await extend_dialogue_subscription("vk",1,"p2"))
    repeat = int(await extend_dialogue_subscription("vk",1,"p2"))
    assert second - first == 30 * 86400
    assert repeat == second


async def test_stars_precheckout_rejects_wrong_amount():
    from bot.handlers.payments import pre_checkout
    query = NS(invoice_payload="product:personal_question",currency="XTR",total_amount=1,answer=AsyncMock())
    await pre_checkout(query)
    assert query.answer.call_args.kwargs["ok"] is False


async def test_vk_generator_failure_does_not_acknowledge_payment(monkeypatch,redis):
    from bot.vk_dialog import payments
    from bot.services.ai_service import AIUnavailable
    monkeypatch.setattr(payments,"_process_vk_q29",AsyncMock(side_effect=AIUnavailable()))
    payment = paid(metadata={"platform":"vk","vk_user_id":"123","tier_key":"q29"})
    result = await payments.handle_vk_payment_webhook(None,_parsed=({"event":"payment.succeeded"},payment,payment["metadata"]))
    assert result.status == 503
    assert not await redis.exists("vk_paid:verified-id")


async def test_vk_included_clarification_survives_failure_and_is_one_time(redis,monkeypatch):
    import time
    from bot.services import dialogue_results
    from bot.services.ai_service import AIUnavailable
    await redis.set("vk:q29:123",json.dumps({"payment_id":"p1","question":"Исходный вопрос", "created_at":time.time()}))
    await redis.set("paid_answer:vk:payment:p1","Полный исходный ответ")
    monkeypatch.setattr(dialogue_results,"generate_business",AsyncMock(side_effect=AIUnavailable()))
    with pytest.raises(AIUnavailable):
        await dialogue_results.vk_clarification(123,"Уточните ответ")
    assert not await redis.exists("vk:clarification:lock:p1")
    async def generate(*args,**kwargs):
        await redis.set("paid_answer:"+kwargs["cache_key"],"Содержательное уточнение")
        return "Содержательное уточнение"
    mock = AsyncMock(side_effect=generate)
    monkeypatch.setattr(dialogue_results,"generate_business",mock)
    assert await dialogue_results.vk_clarification(123,"Уточните ответ") == "Содержательное уточнение"
    assert "Уточнение уже использовано" in await dialogue_results.vk_clarification(123,"Ещё вопрос")
    mock.assert_awaited_once()


async def test_tarot_card_does_not_change_on_retry(redis):
    from bot.services.dialogue_results import stable_card
    cards = [("a","A","Карта A"),("b","B","Карта B")]
    first = await stable_card(redis,"test:card",cards)
    for _ in range(5):
        assert await stable_card(redis,"test:card",cards) == first
