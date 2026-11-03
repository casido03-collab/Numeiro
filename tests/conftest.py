import os
os.environ["BOT_TOKEN"] = "123456:TEST_NOT_A_REAL_BOT_TOKEN"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@127.0.0.1/test"
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database.base import Base
from bot.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def redis(monkeypatch):
    from bot.services import cache
    r = FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", r)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all([User(id=1, telegram_id=1001, first_name="Анна", birth_date="15.03.1990"),
                         User(id=2, telegram_id=1002, first_name="Мария", birth_date="15.03.1990")])
        await session.commit()
    yield maker
    await engine.dispose()
