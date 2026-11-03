"""Real OpenAI + all paid handlers, synthetic users, isolated SQLite/FakeRedis, no chat sends."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ["BOT_TOKEN"] = "123456:TEST_NOT_A_REAL_BOT_TOKEN"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@127.0.0.1/test"


async def main():
    import importlib
    from dotenv import dotenv_values
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from fakeredis.aioredis import FakeRedis
    from database.base import Base
    from bot.models.user import User, UserReport, AIRequest
    from bot.services import ai_service, cache, limits
    from openai import AsyncOpenAI
    key=dotenv_values(ROOT/".env").get("OPENAI_API_KEY")
    if not key: raise RuntimeError("Local OpenAI key is not configured")
    client=AsyncOpenAI(api_key=key,base_url="https://api.openai.com/v1",max_retries=1,timeout=75)
    ai_service._client=client
    ai_service.settings.openai_api_key=key
    cache._redis=FakeRedis(decode_responses=True)
    products=[("mini_reading","reading","select_sphere","sphere:money"),
              ("full_matrix","reading","matrix_start","matrix:start"),
              ("weekly_report","weekly","weekly_sphere_selected","weekly_sphere:money"),
              ("compatibility","compatibility","receive_relation_type","compat:type:love"),
              ("date_selection","dates","generate_dates","dates:run:wedding:60:weekends"),
              ("tarot_card","tarot","tarot_menu","menu:tarot"),
              ("personal_question","question","receive_question",None)]
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        engine=create_async_engine(f"sqlite+aiosqlite:///{Path(tmp)/'synthetic.db'}")
        async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
        maker=async_sessionmaker(engine,expire_on_commit=False)
        async with maker() as s:
            for uid in range(1,8): s.add(User(id=uid,telegram_id=uid,first_name="Тест",birth_date="15.03.1990"))
            await s.commit()
        for uid,(product,module,method,data) in enumerate(products,1):
            await limits.add_credit(uid,product)
            message=NS(chat=NS(id=uid),message_id=1,text="Хочу сменить работу, но боюсь потерять стабильность. Как подготовиться?",
                       edit_text=AsyncMock(),answer=AsyncMock(),answer_photo=AsyncMock(),delete=AsyncMock())
            message.edit_text.return_value=message
            message.answer.return_value=message
            cb=NS(data=data,message=message,answer=AsyncMock())
            state=NS(get_data=AsyncMock(return_value={"partner_date":"01.01.1991","lang":"ru"}),clear=AsyncMock())
            async with maker() as s:
                user=await s.get(User,uid)
                handler=getattr(importlib.import_module(f"bot.handlers.{module}"),method)
                try:
                    if product=="personal_question": await handler(message,state,user,s,"ru")
                    elif product=="compatibility": await handler(cb,state,user,s,"ru")
                    else: await handler(cb,user,s,"ru")
                    report=await s.scalar(select(UserReport).where(UserReport.user_id==uid))
                    usage=await s.scalar(select(AIRequest).where(AIRequest.user_id==uid))
                    results.append({"product":product,"success":True,"model":usage.model,
                        "words":len(report.content.split()),"estimated_usd":usage.estimated_cost,"answer":report.content})
                    print(json.dumps({k:v for k,v in results[-1].items() if k!="answer"},ensure_ascii=False),flush=True)
                except Exception as exc:
                    results.append({"product":product,"success":False,"error_type":type(exc).__name__})
                    print(json.dumps(results[-1]),flush=True)
        await engine.dispose()
    Path(__file__).with_name("all-products-live-results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    await cache._redis.aclose()
    await client.close()
    if not all(x["success"] for x in results):raise SystemExit(1)

if __name__=="__main__":asyncio.run(main())
