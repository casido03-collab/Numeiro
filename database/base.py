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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
