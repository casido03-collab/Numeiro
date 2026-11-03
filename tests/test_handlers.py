from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from bot.models.user import User, UserReport
from bot.services import fulfillment, limits


def callback(data):
    message = NS(edit_text=AsyncMock(), answer=AsyncMock(), answer_photo=AsyncMock(), delete=AsyncMock(),
                 chat=NS(id=1001), message_id=1)
    message.edit_text.return_value = message
    message.answer.return_value = message
    return NS(data=data, message=message, answer=AsyncMock())


@pytest.mark.parametrize("product,module,function,data,state_data", [
    ("mini_reading","reading","select_sphere","sphere:money",None),
    ("full_matrix","reading","matrix_start","matrix:start",None),
    ("weekly_report","weekly","weekly_sphere_selected","weekly_sphere:money",None),
    ("compatibility","compatibility","receive_relation_type","compat:type:love",{"partner_date":"01.01.1991","lang":"ru"}),
    ("date_selection","dates","generate_dates","dates:run:wedding:60:weekends",None),
    ("tarot_card","tarot","tarot_menu","menu:tarot",None),
])
async def test_paid_handler_delivers_and_saves(db, monkeypatch, product,module,function,data,state_data):
    import importlib
    handler = getattr(importlib.import_module(f"bot.handlers.{module}"),function)
    generate = AsyncMock(return_value="Персональный полный разбор. Практический шаг.")
    monkeypatch.setattr(fulfillment,"generate",generate)
    await limits.add_credit(1,product)
    cb = callback(data)
    async with db() as s:
        user = await s.get(User,1)
        kwargs = dict(callback=cb,user=user,session=s,lang="ru")
        if state_data is not None:
            kwargs["state"] = NS(get_data=AsyncMock(return_value=state_data),clear=AsyncMock())
        await handler(**kwargs)
        assert await s.scalar(select(func.count()).select_from(UserReport)) == 1
    assert not await limits.has_credit(1,product)
    assert generate.await_count == 1
    assert "полный разбор" in str(cb.message.edit_text.call_args_list + cb.message.answer.call_args_list)
    prompt = generate.call_args.args[3]
    assert "Не прячьте ответ за доплатой" in prompt


async def test_personal_question_uses_paid_prompt_for_oneoff_customer(db,monkeypatch):
    from bot.handlers.question import receive_question
    from bot.prompts.prompts import PERSONAL_QUESTION_PAID_PROMPT
    generate = AsyncMock(return_value="Ответ и практические шаги.")
    monkeypatch.setattr(fulfillment,"generate",generate)
    await limits.add_credit(1,"personal_question")
    message = callback("").message
    message.text = "Как мне подготовиться к смене работы?"
    state = NS(get_data=AsyncMock(return_value={"lang":"ru"}),clear=AsyncMock())
    async with db() as s:
        await receive_question(message,state,await s.get(User,1),s)
        assert await s.scalar(select(func.count()).select_from(UserReport)) == 1
    assert generate.call_args.args[3] == PERSONAL_QUESTION_PAID_PROMPT("ru")
    assert "question:clarify:" in str(message.edit_text.call_args)


async def test_full_history_visible_without_subscription(db):
    from bot.handlers.reports import reports_category
    from bot.services.reports_service import save_report
    async with db() as s:
        for i in range(7):
            await save_report(s,1,"personal_question",f"Вопрос {i}","Ответ",{})
        await s.commit()
        cb = callback("reports:cat:personal_question:1")
        await reports_category(cb,await s.get(User,1),s,"ru")
        text = cb.message.edit_text.call_args.args[0]
        assert "Вопрос" in text and "скрыто" not in text


def test_date_preferences_are_respected():
    from bot.services.dates import find_favorable_dates
    from datetime import date
    start, end = date(2026,11,3), date(2026,12,3)
    results = find_favorable_dates("wedding",start,to_date=end,weekdays="weekends",birth_date=date(1990,3,15))
    assert len(results) == 5
    assert all(start < item["date_obj"] <= end and item["date_obj"].weekday() >= 5 for item in results)
    assert all(item["personal_energy"] is not None for item in results)


async def test_error_preserves_fsm_and_purchase(db,monkeypatch):
    from bot.middlewares.service_errors import ServiceErrorsMiddleware
    from bot.services.ai_service import AIUnavailable
    state = NS(get_state=AsyncMock(return_value="question:waiting"),get_data=AsyncMock(return_value={"question":"test"}),
               set_state=AsyncMock(),set_data=AsyncMock())
    async with db() as s:
        msg = callback("").message
        await ServiceErrorsMiddleware()(AsyncMock(side_effect=AIUnavailable()),msg,
            {"state":state,"session":s,"user":await s.get(User,1),"lang":"ru"})
        state.set_state.assert_awaited_once_with("question:waiting")
        state.set_data.assert_awaited_once_with({"question":"test"})
        assert "Не удалось" in msg.answer.call_args.args[0]


async def test_tarot_repeat_delivers_owned_answer_without_credit(db,monkeypatch):
    from bot.handlers.tarot import tarot_menu
    generate = AsyncMock(return_value="Сохранённая карта дня и полезный шаг.")
    monkeypatch.setattr(fulfillment,"generate",generate)
    await limits.add_credit(1,"tarot_card")
    async with db() as s:
        user = await s.get(User,1)
        await tarot_menu(callback("menu:tarot"),user,s)
        cb = callback("menu:tarot")
        await tarot_menu(cb,user,s)
        assert "Сохранённая карта" in cb.message.edit_text.call_args.args[0]
        assert await s.scalar(select(func.count()).select_from(UserReport)) == 1
    generate.assert_awaited_once()


async def test_notifications_stop_does_not_block_direct_replies(redis):
    from bot.services.notifications import NotificationBot, set_muted
    actual_bot = NS(send_message=AsyncMock())
    notifier = NotificationBot(actual_bot)
    await set_muted("tg",1001,True)
    await notifier.send_message(1001,"Reminder")
    actual_bot.send_message.assert_not_awaited()
    await actual_bot.send_message(1001,"Payment received")
    actual_bot.send_message.assert_awaited_once()
    await set_muted("tg",1001,False)
    await notifier.send_message(1001,"Reminder")
    assert actual_bot.send_message.await_count == 2
