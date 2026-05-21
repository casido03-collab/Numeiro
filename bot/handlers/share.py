"""Share-кнопки — отправить прогноз/совместимость друзьям."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.models.user import User

router = Router()
logger = logging.getLogger(__name__)

# Кешируем username бота, чтобы не делать get_me() на каждый тап
_bot_username: str | None = None


async def _get_bot_username(bot) -> str:
    global _bot_username
    if not _bot_username:
        me = await bot.get_me()
        _bot_username = me.username
    return _bot_username


@router.callback_query(F.data.startswith("share:"))
async def share_result(callback: CallbackQuery, user: User):
    # Отвечаем на callback СРАЗУ — до любых async-операций,
    # чтобы не словить "query is too old" от Telegram (таймаут 30 сек)
    await callback.answer()

    try:
        parts = callback.data.split(":")
        share_type = parts[1] if len(parts) > 1 else "reading"

        bot_username = await _get_bot_username(callback.bot)

        text_map = {
            "reading": "🔮 Только что получил свой нумерологический разбор — очень точно!",
            "compat": "💞 Проверил совместимость — результат удивил!",
        }
        share_text = text_map.get(share_type, "✨ Попробуй персональный эзотерический разбор!")

        deep_link = f"https://t.me/{bot_username}?start=ref_{user.telegram_id}"

        await callback.message.answer(
            f"📤 *Поделись с друзьями:*\n\n"
            f"{share_text}\n\n"
            f"👉 {deep_link}",
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
    except Exception:
        logger.exception("share_result failed for user %s data=%s", user.telegram_id, callback.data)
