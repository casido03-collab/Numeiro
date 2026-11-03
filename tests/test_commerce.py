import asyncio
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from bot.services import ai_service, fulfillment, limits
from bot.models.user import UserReport, PaidResult


def completion(text="Готовый содержательный ответ.", reason="stop", refusal=None):
    return NS(choices=[NS(message=NS(content=text, refusal=refusal), finish_reason=reason)],
              usage=NS(prompt_tokens=500, completion_tokens=800))


@pytest.mark.parametrize("reply", [completion(""), completion(reason="length"), completion(refusal="refused")])
async def test_no_partial_or_empty_paid_answer(monkeypatch, reply):
    create = AsyncMock(return_value=reply)
    monkeypatch.setattr(ai_service, "_get_client", lambda: NS(chat=NS(completions=NS(create=create))))
    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.complete("system", "user")


async def test_direct_openai_params(monkeypatch):
    create = AsyncMock(return_value=completion())
    monkeypatch.setattr(ai_service, "_get_client", lambda: NS(chat=NS(completions=NS(create=create))))
    await ai_service.complete("system", "user", "complex", 4200)
    kwargs = create.call_args.kwargs
    assert kwargs["model"] == "gpt-6.1-terra"
    assert kwargs["max_completion_tokens"] == 4200
    assert kwargs["extra_body"]["reasoning_effort"] == "none"
    assert "temperature" not in kwargs and not kwargs["model"].startswith("openai/")


async def test_unavailable_has_no_demo(monkeypatch):
    monkeypatch.setattr(ai_service, "_get_client", lambda: None)
    with pytest.raises(ai_service.AIUnavailable):
        await ai_service.complete("system", "user")


async def test_installed_sdk_accepts_new_model_parameters(monkeypatch):
    import httpx, json
    from openai import AsyncOpenAI
    seen = []
    def handle(request):
        seen.append(json.loads(request.content))
        assert request.url.host == "api.openai.com"
        return httpx.Response(200,json={"id":"test","object":"chat.completion","created":1,"model":"gpt-6-luna",
            "choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"Ответ"}}],
            "usage":{"prompt_tokens":5,"completion_tokens":8,"total_tokens":13}})
    client = AsyncOpenAI(api_key="test",base_url="https://api.openai.com/v1",http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    monkeypatch.setattr(ai_service,"_get_client",lambda:client)
    await ai_service.complete("system","synthetic question")
    assert seen[0]["reasoning_effort"] == "none"
    assert seen[0]["max_completion_tokens"] == 1600
    await client.close()


async def test_too_short_paid_response_is_not_delivered(db,monkeypatch):
    monkeypatch.setattr(ai_service,"complete",AsyncMock(return_value=("Очень коротко.","gpt-6-luna",None)))
    async with db() as s:
        with pytest.raises(ai_service.AIUnavailable):
            await ai_service.generate(s,1,"full_matrix","system","question")


async def test_concurrent_debits_and_idempotency(redis):
    await limits.add_credit(1, "personal_question", amount=1)
    results = await asyncio.gather(*(limits.consume_product(1, "personal_question", str(i)) for i in range(15)))
    assert sum(results) == 1
    assert await redis.get("oneoff:personal_question:1") == "0"
    winner = str(results.index(True))
    assert await limits.consume_product(1, "personal_question", winner)
    assert await redis.get("oneoff:personal_question:1") == "0"


async def test_vip_renewal_carries_days_and_quota(redis):
    await limits.activate_vip(1, days=10)
    await limits.use_vip_limit(1, "personal_question")
    await limits.activate_vip(1, days=30, event_id="renewal-1")
    await limits.activate_vip(1, days=30, event_id="renewal-1")
    assert 40 * 86400 - 10 <= await redis.ttl("vip:1") <= 40 * 86400
    assert await redis.get("vip_limit:personal_question:1") == "59"
    assert abs(await redis.ttl("vip_limit:personal_question:1") - await redis.ttl("vip:1")) <= 1


async def test_exhausted_vip_uses_purchased_credit(redis):
    await limits.activate_vip(1)
    await redis.set("vip_limit:personal_question:1", "0")
    await limits.add_credit(1, "personal_question")
    assert await limits.can_use_product(1, "personal_question")
    assert await limits.consume_product(1, "personal_question", "fallback")
    assert not await limits.has_credit(1, "personal_question")


async def test_grant_retry_does_not_duplicate_or_expire(redis):
    await limits.add_credit(1, "mini_reading", event_id="paid-1")
    await limits.add_credit(1, "mini_reading", event_id="paid-1")
    assert await redis.get("oneoff:mini_reading:1") == "1"
    assert await redis.ttl("oneoff:mini_reading:1") == -1


async def request(session, context=None):
    return await fulfillment.generate_paid_report(session, 1, "personal_question", "personal_question", "Вопрос",
        context or {"request": 1}, "paid prompt", metadata={"question": "Что делать?"})


async def test_ai_failure_does_not_spend_or_save(db, redis, monkeypatch):
    await limits.add_credit(1, "personal_question")
    monkeypatch.setattr(fulfillment, "generate", AsyncMock(side_effect=ai_service.AIUnavailable()))
    async with db() as s:
        with pytest.raises(ai_service.AIUnavailable):
            await request(s)
        assert await s.scalar(select(func.count()).select_from(PaidResult)) == 0
    assert await limits.has_credit(1, "personal_question")


async def test_fulfilled_result_is_durable_and_retry_is_free(db, redis, monkeypatch):
    await limits.add_credit(1, "personal_question")
    generate = AsyncMock(return_value="Полный ответ без доплаты.")
    monkeypatch.setattr(fulfillment, "generate", generate)
    async with db() as s:
        first = await request(s)
        report_id = first.id
    async with db() as s:
        repeat = await request(s)
        assert repeat.id == report_id
        assert await s.scalar(select(func.count()).select_from(UserReport)) == 1
    generate.assert_awaited_once()
    assert not await limits.has_credit(1, "personal_question")


async def test_failure_after_debit_recovers_without_second_charge(db, redis, monkeypatch):
    await limits.add_credit(1, "personal_question", amount=2)
    monkeypatch.setattr(fulfillment, "generate", AsyncMock(return_value="Полный ответ."))
    async with db() as s:
        commit = s.commit
        calls = 0
        async def fail_second_commit():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("database temporarily unavailable")
            await commit()
        monkeypatch.setattr(s, "commit", fail_second_commit)
        with pytest.raises(RuntimeError):
            await request(s)
        await s.rollback()
    assert await redis.get("oneoff:personal_question:1") == "1"
    async with db() as s:
        await fulfillment.recover_pending(s, 1)
        assert await s.scalar(select(func.count()).select_from(UserReport)) == 1
    assert await redis.get("oneoff:personal_question:1") == "1"


def test_result_keys_include_customer_language_period_and_prompt():
    key = fulfillment.result_key
    assert key(1,"weekly","ru",{"start":"2026-11-02"}) != key(2,"weekly","ru",{"start":"2026-11-02"})
    assert key(1,"weekly","ru",{"start":"2026-11-02"}) != key(1,"weekly","en",{"start":"2026-11-02"})
    assert key(1,"weekly","ru",{"start":"2026-11-02"}) != key(1,"weekly","ru",{"start":"2026-11-03"})


async def test_one_clarification_owned_and_within_24h(db, monkeypatch):
    from bot.services import clarification
    from bot.services.reports_service import save_report
    monkeypatch.setattr(clarification, "generate", AsyncMock(return_value="Ответ на уточнение."))
    async with db() as s:
        report = await save_report(s,1,"personal_question","Вопрос","Ответ",{"question":"Почему?"})
        await s.commit()
        with pytest.raises(clarification.ClarificationUnavailable):
            await clarification.clarify(s,2,report.id,"Уточнение?","ru")
        first = await clarification.clarify(s,1,report.id,"Уточнение?","ru")
        again = await clarification.clarify(s,1,report.id,"Другой вопрос?","ru")
        assert first.id == again.id
        clarification.generate.assert_awaited_once()
        with pytest.raises(clarification.ClarificationUnavailable):
            await clarification.clarify(s,1,first.id,"Ещё вопрос?","ru")
        old = await save_report(s,1,"personal_question","Старый вопрос","Ответ",{})
        old.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        await s.commit()
        with pytest.raises(clarification.ClarificationUnavailable):
            await clarification.clarify(s,1,old.id,"Уточнение?","ru")


async def test_full_text_delivery_without_loss():
    from bot.utils import safe_edit_ai, split_answer
    text = ("Полный разбор 🌙\n" * 800)
    chunks = split_answer(text)
    assert "".join(chunks) == text
    assert all(len(c.encode("utf-16-le")) // 2 <= 3500 for c in chunks)
    msg = NS(edit_text=AsyncMock(), answer=AsyncMock())
    await safe_edit_ai(msg, text, reply_markup="buttons")
    assert msg.edit_text.call_args.kwargs["reply_markup"] is None
    assert msg.answer.call_args.kwargs["reply_markup"] == "buttons"
    assert msg.answer.await_count == len(chunks) - 1


def test_customer_contracts_have_current_prices():
    from bot.services.catalog import product_offer, FREE_SUMMARY
    from config import PRODUCTS
    for key, info in PRODUCTS.items():
        assert f'{info["price_rub"]} ₽' in product_offer(key,"ru")
        assert f'{info["price_stars"]} ⭐' in product_offer(key,"en")
    assert "24" in product_offer("personal_question")
    assert "одна" in FREE_SUMMARY["ru"]
