"""Спонсорская подписка — плашка с обязательной подпиской на канал."""
import logging
import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.handlers.admin import is_admin as is_admin_id

logger = logging.getLogger(__name__)
router = Router()

# ─── Redis-ключи ──────────────────────────────────────────────────────────────

SPONSOR_ENABLED_KEY = "sponsor:enabled"
SPONSOR_LINK_KEY    = "sponsor:link"
SPONSOR_CHANNEL_KEY = "sponsor:channel"  # @username или chat_id

_SPONSOR_TEXT = (
    "Душа моя, я помогла уже более 8 000 людей обрести свой жизненный путь. "
    "Один из моих клиентов — молодой состоятельный человек — пожертвовал на разработку этого бота. "
    "В благодарность я прошу подписаться на его канал, "
    "и после этого я безвозмездно выслушаю ваш вопрос. 🌙"
)


# ─── Вспомогательные ──────────────────────────────────────────────────────────

async def get_sponsor_state() -> dict:
    """Вернуть текущее состояние спонсора из Redis."""
    from bot.services.cache import get_redis
    r = await get_redis()
    enabled = (await r.get(SPONSOR_ENABLED_KEY) or b"0").decode() == "1"
    link    = (await r.get(SPONSOR_LINK_KEY) or b"").decode()
    channel = (await r.get(SPONSOR_CHANNEL_KEY) or b"").decode()
    return {"enabled": enabled, "link": link, "channel": channel}


def _extract_channel(link: str) -> str:
    """Извлечь @username из ссылки."""
    link = link.strip()
    if link.startswith("@"):
        return link
    m = re.search(r"t\.me/([^/?]+)", link)
    if m:
        return "@" + m.group(1)
    return link


async def is_subscribed(bot: Bot, user_id: int, channel: str) -> bool:
    """Проверить подписку пользователя на канал."""
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning("Sponsor check failed for %s in %s: %s", user_id, channel, e)
        return False


def sponsor_keyboard(link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подписаться", url=link)],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="sponsor:check")],
    ])


async def show_sponsor_screen(target, bot: Bot, link: str) -> None:
    """Показать плашку спонсора. target — Message или CallbackQuery."""
    kb = sponsor_keyboard(link)
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(_SPONSOR_TEXT, reply_markup=kb)
        except Exception:
            await target.message.answer(_SPONSOR_TEXT, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(_SPONSOR_TEXT, reply_markup=kb)


# ─── Проверка подписки ────────────────────────────────────────────────────────

async def check_sponsor_required(user_id: int, bot: Bot) -> bool:
    """Вернуть True если нужна проверка И пользователь НЕ подписан."""
    state = await get_sponsor_state()
    if not state["enabled"] or not state["channel"]:
        return False
    return not await is_subscribed(bot, user_id, state["channel"])


# ─── Хендлер кнопки «Проверить подписку» ─────────────────────────────────────

@router.callback_query(F.data == "sponsor:check")
async def check_subscription(callback: CallbackQuery):
    from bot.keyboards.main import main_menu
    from bot.handlers.start import random_header

    state = await get_sponsor_state()
    if not state["enabled"] or not state["channel"]:
        # Плашка выключена — пускаем в меню
        name = callback.from_user.first_name or None
        await callback.message.edit_text(random_header(name), reply_markup=main_menu())
        await callback.answer()
        return

    subscribed = await is_subscribed(callback.message.bot, callback.from_user.id, state["channel"])
    if subscribed:
        name = callback.from_user.first_name or None
        await callback.message.edit_text(random_header(name), reply_markup=main_menu())
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer(
            "❌ Вы ещё не подписались на канал. Подпишитесь и нажмите «Проверить» снова.",
            show_alert=True,
        )


# ─── Админ-команды ────────────────────────────────────────────────────────────

@router.message(Command("sponsor"))
async def cmd_sponsor_toggle(message: Message):
    if not is_admin_id(message.from_user.id):
        return
    from bot.services.cache import get_redis
    r = await get_redis()
    current = (await r.get(SPONSOR_ENABLED_KEY) or b"0").decode()
    new_val  = "0" if current == "1" else "1"
    await r.set(SPONSOR_ENABLED_KEY, new_val)

    state = "✅ ВКЛЮЧЕНА" if new_val == "1" else "❌ ВЫКЛЮЧЕНА"
    await message.answer(
        f"🎯 Плашка спонсора: *{state}*\n\n"
        f"При включении все разделы бота требуют подписки на канал.\n"
        f"Ссылка: {(await r.get(SPONSOR_LINK_KEY) or b'').decode() or 'не задана'}",
        parse_mode="Markdown",
    )


@router.message(Command("link"))
async def cmd_set_link(message: Message):
    """Установить ссылку для кнопки 'Подписаться'."""
    if not is_admin_id(message.from_user.id):
        return
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Использование: `/link <ссылка>`\n\n"
            "Пример: `/link https://t.me/+abc123`\n\n"
            "Это ссылка для кнопки «Подписаться».\n"
            "Для приватного канала также укажите ID канала: `/channel_id -1001234567890`",
            parse_mode="Markdown",
        )
        return

    link = parts[1].strip()
    from bot.services.cache import get_redis
    r = await get_redis()
    await r.set(SPONSOR_LINK_KEY, link)

    # Если публичный канал — сразу извлекаем username
    channel = _extract_channel(link)
    if not channel.startswith("@+"):  # публичная ссылка
        await r.set(SPONSOR_CHANNEL_KEY, channel)
        await message.answer(
            f"✅ Ссылка сохранена: {link}\nКанал для проверки: `{channel}`",
            parse_mode="Markdown",
        )
    else:
        await message.answer(
            f"✅ Ссылка для кнопки сохранена: {link}\n\n"
            "⚠️ Это приватный канал. Укажите числовой ID канала для проверки подписки:\n"
            "`/channel_id -1001234567890`\n\n"
            "ID канала можно узнать переслав любое сообщение из канала боту @userinfobot",
            parse_mode="Markdown",
        )


@router.message(Command("channel_id"))
async def cmd_set_channel_id(message: Message):
    """Установить ID приватного канала для проверки подписки."""
    if not is_admin_id(message.from_user.id):
        return
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Использование: `/channel_id <ID>`\n\n"
            "Пример: `/channel_id -1001234567890`\n\n"
            "💡 Как узнать ID: перешли любое сообщение из канала боту @userinfobot",
            parse_mode="Markdown",
        )
        return

    channel_id = parts[1].strip()
    if not channel_id.lstrip("-").isdigit():
        await message.answer("❌ ID должен быть числом, например: `-1001234567890`", parse_mode="Markdown")
        return

    from bot.services.cache import get_redis
    r = await get_redis()
    await r.set(SPONSOR_CHANNEL_KEY, channel_id)

    # Тест проверки
    try:
        member = await message.bot.get_chat_member(chat_id=int(channel_id), user_id=message.from_user.id)
        status = member.status
        await message.answer(
            f"✅ ID канала сохранён: `{channel_id}`\n\nТест: ваш статус в канале — `{status}`\n\n"
            "Бот должен быть администратором канала для проверки подписчиков.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.answer(
            f"⚠️ ID сохранён: `{channel_id}`, но проверка не прошла: `{e}`\n\n"
            "Убедитесь что бот добавлен в канал как администратор.",
            parse_mode="Markdown",
        )
