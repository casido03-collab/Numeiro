import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from datetime import timedelta
import pytest
from sqlalchemy import select, func
from bot.models.user import User, UserReport, Payment
from bot.models.vk import VKAccount, VKOrder, VKInbox, VKOutbox, utcnow
from bot.vk_menu.queue import enqueue, process_event, deliver, chunks
from bot.vk_menu import keyboards as kb
from bot.vk_menu import controller, payments
from bot.services.limits import add_credit
from bot.services.ai_service import AIUnavailable


class Driver:
    def __init__(self, maker, uid=501):
        self.maker, self.uid, self.seq = maker, uid, 0
        self.api = SimpleNamespace(users=SimpleNamespace(get=AsyncMock(return_value=[SimpleNamespace(first_name="Анна")])),
            messages=SimpleNamespace(send=AsyncMock(return_value=123)))

    async def event(self, text="", cmd="", internal=None):
        self.seq += 1
        msg = {"text":text}
        if cmd:
            msg["payload"] = json.dumps({"a":cmd})
        if internal:
            msg.update(internal)
        async with self.maker() as session:
            key = f"test:{self.uid}:{self.seq}"
            await enqueue(session, key, self.uid, msg)
            eid = await session.scalar(select(VKInbox.id).where(VKInbox.event_key==key))
        await process_event(self.maker, self.api, eid)
        async with self.maker() as session:
            return list((await session.scalars(select(VKOutbox).where(VKOutbox.key.like(key+":%")))).all())

    async def account(self):
        async with self.maker() as session:
            account = await session.get(VKAccount, self.uid)
            return account, await session.get(User, account.user_id)

    async def setup(self):
        await self.event("Начать")
        await self.event(cmd="edit:birth")
        await self.event("15.03.1990")

    async def draft(self, product):
        await self.event(cmd=f"begin:{product}")
        if product=="personal_question":
            await self.event("Как решиться на переход на новую работу?")
        elif product in ("mini_reading", "weekly_report"):
            await self.event(cmd="sphere:work")
        elif product=="compatibility":
            await self.event("21.07.1988")
            await self.event(cmd="relation:love")
        elif product=="date_selection":
            await self.event(cmd="event:travel")
            await self.event(cmd="days:30")
            await self.event(cmd="weekdays:weekends")
        async with self.maker() as session:
            return await session.scalar(select(VKOrder).where(VKOrder.vk_id==self.uid).order_by(VKOrder.created_at.desc()).limit(1))


@pytest.fixture
def ai(monkeypatch):
    result = AsyncMock(return_value="Разбор ситуации. " * 170)
    monkeypatch.setattr("bot.services.fulfillment.generate", result)
    return result


@pytest.mark.asyncio
async def test_menu_identity_and_full_catalog(db):
    d = Driver(db, uid=1001)  # Same public number as existing Telegram user.
    messages = await d.event("Начать")
    account, user = await d.account()
    assert user.id != 1 and user.telegram_id is None
    catalog = await d.event(cmd="catalog")
    assert len(catalog) == 1  # Opening services should not repeat the greeting.
    assert "Личный вопрос" in catalog[0].body["message"]
    assert "₽" not in json.dumps([m.body for m in messages + catalog], ensure_ascii=False)
    keyboard = json.loads(catalog[0].body["keyboard"])
    next_button = next(b for row in keyboard["buttons"] for b in row if b["action"]["label"] == "Ещё услуги →")
    second_page = await d.event(cmd=json.loads(next_button["action"]["payload"])["a"])
    assert len(second_page) == 1
    assert "Совместимость пары" in second_page[0].body["message"]
    assert "VIP на 30 дней" in second_page[0].body["message"]
    assert "₽" not in json.dumps(second_page[0].body, ensure_ascii=False)
    messages += second_page
    commands = []
    for msg in messages:
        keyboard = json.loads(msg.body["keyboard"])
        for row in keyboard["buttons"]:
            for button in row:
                commands.append(json.loads(button["action"]["payload"])["a"])
                assert button["color"] in ("primary", "secondary", "positive", "negative")
    assert {"product:"+p for p in kb.ORDER}.issubset(commands)
    assert {"support", "history", "free", "vip"}.issubset(commands)
    back_button = next(b for row in json.loads(second_page[0].body["keyboard"])["buttons"] for b in row if b["action"]["label"] == "← Назад")
    first_page = await d.event(cmd=json.loads(back_button["action"]["payload"])["a"])
    assert "Личный вопрос" in first_page[0].body["message"]
    for product in kb.ORDER:
        details = await d.event(cmd=f"product:{product}")
        assert f"{controller.PRODUCTS[product]['price_rub']} ₽" in details[0].body["message"]
        assert "Что вы получите:" in details[0].body["message"]
        assert "ЮKassa" in details[0].body["message"]
    vip = await d.event(cmd="vip")
    assert "1999 ₽" in vip[0].body["message"]
    assert "Автосписаний нет" in vip[0].body["message"]


@pytest.mark.parametrize("product", kb.ORDER)
@pytest.mark.asyncio
async def test_every_vk_product_fulfills_once_and_reopens(db, redis, ai, product):
    d=Driver(db)
    await d.setup()
    order=await d.draft(product)
    assert order and order.product==product
    await add_credit(order.user_id, product)
    messages=await d.event(cmd=f"run:{order.id}")
    assert any("Разбор ситуации" in m.body["message"] for m in messages)
    await d.event(cmd=f"run:{order.id}")
    assert ai.await_count==1
    assert await redis.get(f"oneoff:{product}:{order.user_id}")=="0"
    async with db() as session:
        saved=await session.get(VKOrder,order.id)
        assert saved.status=="fulfilled" and saved.report_id
        assert await session.scalar(select(func.count()).select_from(UserReport).where(UserReport.user_id==order.user_id))==1


@pytest.mark.asyncio
async def test_payment_freezes_question_and_grants_once(db, redis, ai, monkeypatch):
    d=Driver(db)
    await d.setup()
    order=await d.draft("personal_question")
    monkeypatch.setattr(payments.settings,"yookassa_shop_id","test-shop")
    monkeypatch.setattr(payments.settings,"yookassa_secret_key","test-secret")
    create=AsyncMock(return_value={"id":"pay-vk-1","confirmation_url":"https://yookassa.ru/test-checkout","status":"pending"})
    monkeypatch.setattr(payments,"create_payment",create)
    await d.event(cmd=f"buy:{order.id}")
    messages=await d.event("anna@example.ru")
    assert any('https://yookassa.ru/test-checkout' in m.body.get("keyboard","") for m in messages)
    assert create.call_args.kwargs["idempotency_key"]==order.id
    assert create.call_args.kwargs["email"]=="anna@example.ru"
    await d.event(cmd=f"buy:{order.id}")
    await d.event(cmd="email:saved")
    assert create.await_count==1
    meta=create.call_args.args[5]
    p={"id":"pay-vk-1","status":"succeeded","paid":True,"amount":{"value":"29.00","currency":"RUB"},"metadata":meta}
    await payments.accept_payment(db,p)
    await payments.accept_payment(db,p)
    assert await redis.get(f"oneoff:personal_question:{order.user_id}")=="1"
    async with db() as session:
        assert await session.scalar(select(func.count()).select_from(Payment))==1
        eid=await session.scalar(select(VKInbox.id).where(VKInbox.event_key=="vk-yk:pay-vk-1"))
    await d.event(cmd="begin:personal_question")
    await d.event("Новый вопрос о том, как наладить отношения с семьёй?")
    await process_event(db,d.api,eid)
    assert "новую работу" in json.loads(ai.call_args.args[4])["question"]
    assert await redis.get(f"oneoff:personal_question:{order.user_id}")=="0"


@pytest.mark.asyncio
async def test_failed_generation_keeps_credit_and_retry(db,redis,ai):
    d=Driver(db)
    await d.setup()
    order=await d.draft("full_matrix")
    await add_credit(order.user_id,order.product)
    ai.side_effect=AIUnavailable("temporary")
    msgs=await d.event(cmd=f"run:{order.id}")
    assert any("доступ сохранён" in m.body["message"] for m in msgs)
    assert await redis.get(f"oneoff:full_matrix:{order.user_id}")=="1"
    ai.side_effect=None
    await d.event(cmd=f"run:{order.id}")
    assert await redis.get(f"oneoff:full_matrix:{order.user_id}")=="0"


@pytest.mark.asyncio
async def test_foreign_order_and_report_are_not_accessible(db,ai):
    a,b=Driver(db,501),Driver(db,502)
    await a.setup()
    await b.setup()
    order=await a.draft("mini_reading")
    await add_credit(order.user_id,order.product)
    await a.event(cmd=f"run:{order.id}")
    async with db() as session:
        saved=await session.get(VKOrder,order.id)
        report_id=saved.report_id
    msgs=await b.event(cmd=f"run:{order.id}")
    assert "не найден" in msgs[-1].body["message"]
    msgs=await b.event(cmd=f"report:{report_id}")
    assert "не найден" in msgs[-1].body["message"]
    assert ai.await_count==1


@pytest.mark.asyncio
async def test_support_silence_resume_and_paid_credit(db,redis,ai):
    d=Driver(db)
    await d.setup()
    order=await d.draft("mini_reading")
    await add_credit(order.user_id,order.product)
    msgs=await d.event(cmd="support")
    assert len(msgs)==1 and msgs[0].body["_support_notice"]
    assert (await d.account())[0].manual_support
    assert await d.event("Мне нужна помощь с оплатой") == []
    assert await d.event(cmd="menu") == []
    assert await d.event(internal={"internal":"paid", "order_id":order.id}) == []
    assert ai.await_count==0
    assert await redis.get(f"oneoff:mini_reading:{order.user_id}")=="1"
    assert await d.event(cmd="resume")
    assert not (await d.account())[0].manual_support
    await d.event(cmd=f"run:{order.id}")
    assert ai.await_count==1


@pytest.mark.asyncio
async def test_free_daily_reopen_and_profile_change(db, monkeypatch):
    daily=AsyncMock(return_value="Энергия дня: спокойный темп и конкретные дела.")
    monkeypatch.setattr("bot.vk_menu.readings.generate",daily)
    d=Driver(db)
    await d.setup()
    first=await d.event(cmd="daily:daily_energy")
    await d.event(cmd="edit:name")
    await d.event("Новое имя")
    second=await d.event(cmd="daily:daily_energy")
    assert daily.await_count==1
    assert first[-1].body["message"]==second[-1].body["message"]


@pytest.mark.asyncio
async def test_callback_authentication_queue_and_immediate_operator_pause(db,monkeypatch):
    from bot.vk_dialog import callback
    monkeypatch.setattr(callback,"async_session_maker",db)
    monkeypatch.setattr(callback,"_vk_api",object())
    monkeypatch.setattr(callback.settings,"vk_callback_secret","test-secret")
    d=Driver(db)
    await d.setup()
    payload={"group_id":200332918,"secret":"bad","type":"message_new","object":{"message":{
        "from_id":501,"peer_id":501,"conversation_message_id":42,"text":"поддержка"}}}
    request=SimpleNamespace(json=AsyncMock(side_effect=lambda:payload))
    assert (await callback.handle_vk_callback(request)).status==403
    payload["secret"]="test-secret"
    assert (await callback.handle_vk_callback(request)).text=="ok"
    assert (await d.account())[0].manual_support
    assert (await callback.handle_vk_callback(request)).text=="ok"
    async with db() as session:
        assert await session.scalar(select(func.count()).select_from(VKInbox).where(VKInbox.event_key=="vk:200332918:501:42"))==1


@pytest.mark.asyncio
async def test_delivery_retry_id_stable_and_internal_flags_removed(db):
    api=SimpleNamespace(messages=SimpleNamespace(send=AsyncMock()))
    row=VKOutbox(key="reply-test",vk_id=501,body={"message":"hello","_support_notice":True})
    await deliver(db,api,row)
    first=api.messages.send.call_args.kwargs
    await deliver(db,api,row)
    assert api.messages.send.call_args.kwargs==first
    assert "_support_notice" not in first and first["random_id"]>0
    text="А"*8000
    parts=list(chunks(text))
    assert ''.join(parts)==text and max(map(len,parts))<=3000


@pytest.mark.asyncio
async def test_clarification_included_once_then_reopened(db, ai, monkeypatch):
    followup=AsyncMock(return_value="Уточнение с конкретными шагами. "*30)
    monkeypatch.setattr("bot.services.clarification.generate",followup)
    d=Driver(db)
    await d.setup()
    order=await d.draft("personal_question")
    await add_credit(order.user_id,order.product)
    await d.event(cmd=f"run:{order.id}")
    async with db() as session:
        report_id=(await session.get(VKOrder,order.id)).report_id
    await d.event(cmd=f"clarify:{report_id}")
    await d.event("Как лучше начать разговор с руководителем?")
    msgs=await d.event(cmd=f"clarify:{report_id}")
    assert "Уточнение с конкретными" in msgs[-1].body["message"]
    assert followup.await_count==1
    async with db() as session:
        report=await session.get(UserReport,report_id)
        report.metadata_json={}
        report.created_at=utcnow()-timedelta(hours=25)
        await session.commit()
    msgs=await d.event(cmd=f"clarify:{report_id}")
    assert "истекли" in msgs[-1].body["message"]


@pytest.mark.asyncio
async def test_payment_owner_amount_and_vip_renewal(db,redis):
    d=Driver(db)
    await d.setup()
    account,user=await d.account()
    async def new_vip(pid):
        oid=str(__import__('uuid').uuid4())
        async with db() as session:
            session.add(VKOrder(id=oid,user_id=user.id,vk_id=501,product="vip",amount=1999,details={},status="pending",payment_id=pid))
            await session.commit()
        return {"id":pid,"status":"succeeded","paid":True,"amount":{"value":"1999.00","currency":"RUB"},
            "metadata":{"platform":"vk_catalog","product_type":"product","product_key":"vip","vk_user_id":"501","user_id":str(user.id),"order_id":oid}}
    first=await new_vip("vip-1")
    wrong=json.loads(json.dumps(first));wrong["metadata"]["vk_user_id"]="502"
    with pytest.raises(ValueError):
        await payments.accept_payment(db,wrong)
    wrong=json.loads(json.dumps(first));wrong["amount"]["value"]="1.00"
    with pytest.raises(ValueError):
        await payments.accept_payment(db,wrong)
    await payments.accept_payment(db,first)
    await payments.accept_payment(db,first)
    assert await redis.get(f"vip_limit:personal_question:{user.id}")=="30"
    ttl=await redis.ttl(f"vip:{user.id}")
    await payments.accept_payment(db,await new_vip("vip-2"))
    assert await redis.get(f"vip_limit:personal_question:{user.id}")=="60"
    assert await redis.ttl(f"vip:{user.id}") >= ttl+30*86400-2


@pytest.mark.asyncio
async def test_manual_operator_reply_pauses_but_own_bot_reply_does_not(db,monkeypatch):
    from bot.vk_dialog import callback
    monkeypatch.setattr(callback,"async_session_maker",db)
    monkeypatch.setattr(callback,"_vk_api",object())
    monkeypatch.setattr(callback.settings,"vk_callback_secret","test-secret")
    d=Driver(db); await d.setup()
    payload={"group_id":200332918,"secret":"test-secret","type":"message_reply","object":{"peer_id":501,"text":"Здравствуйте"}}
    request=SimpleNamespace(json=AsyncMock(side_effect=lambda:payload))
    assert (await callback.handle_vk_callback(request)).text=="ok"
    assert not (await d.account())[0].manual_support
    payload["object"]["admin_author_id"]=123
    assert (await callback.handle_vk_callback(request)).text=="ok"
    assert (await d.account())[0].manual_support


@pytest.mark.asyncio
async def test_card_of_day_survives_name_change_without_second_purchase(db,ai):
    d=Driver(db);await d.setup()
    order=await d.draft("tarot_card")
    await add_credit(order.user_id,order.product)
    await d.event(cmd=f"run:{order.id}")
    await d.event(cmd="edit:name");await d.event("Другое имя")
    messages=await d.event(cmd="begin:tarot_card")
    assert any("без нового списания" in m.body["message"] for m in messages)
    assert ai.await_count==1
