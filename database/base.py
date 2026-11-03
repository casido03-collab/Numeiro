from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,           # базовый пул соединений
    max_overflow=20,        # дополнительных соединений сверх пула
    pool_timeout=30,        # ждать свободное соединение не более 30 сек
    pool_recycle=1800,      # пересоздавать соединения каждые 30 мин
    pool_pre_ping=True,     # проверять соединение перед использованием (лечит "протухшие" коннекты)
)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def create_tables():
    from bot.models import vk  # register the VK catalog, inbox and outbox tables
    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            from sqlalchemy import inspect, text
            columns = await conn.run_sync(lambda c: inspect(c).get_columns("users") if inspect(c).has_table("users") else [])
            if any(c["name"] == "telegram_id" and not c["nullable"] for c in columns):
                await conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL"))
        await conn.run_sync(Base.metadata.create_all)
