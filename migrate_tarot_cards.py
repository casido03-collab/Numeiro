"""
Миграция: добавить столбец tarot_cards в таблицу usage_limits.
Запустить один раз: python migrate_tarot_cards.py
"""
import asyncio
from sqlalchemy import text
from database.base import engine


async def run():
    async with engine.begin() as conn:
        # Проверяем, существует ли уже столбец
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='usage_limits' AND column_name='tarot_cards'"
        ))
        row = result.fetchone()
        if row:
            print("✅ Столбец tarot_cards уже существует — миграция не нужна.")
        else:
            await conn.execute(text(
                "ALTER TABLE usage_limits ADD COLUMN tarot_cards INTEGER NOT NULL DEFAULT 0"
            ))
            print("✅ Столбец tarot_cards успешно добавлен.")


if __name__ == "__main__":
    asyncio.run(run())
