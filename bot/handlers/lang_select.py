"""Выбор языка — первый экран при /start для новых пользователей."""
import logging
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.i18n.translations import t, save_user_lang

router = Router()
logger = logging.getLogger(__name__)

_SUPPORTED_LANGS = ("ru", "en", "fa", "tr")


def lang_select_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="ob:lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="ob:lang:en"),
        ],
        [
            InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="ob:lang:fa"),
            InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="ob:lang:tr"),
        ],
    ])


async def send_lang_selection(message: Message) -> None:
    """Отправить экран выбора языка (вызывается из start.py)."""
    await message.answer(
        "🌍 Выберите язык / Choose your language / زبان خود را انتخاب کنید / Dilinizi seçin:",
        reply_markup=lang_select_keyboard(),
    )


@router.callback_query(F.data.startswith("ob:lang:"))
async def lang_selected(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    """Пользователь выбрал язык → сохраняем, показываем экран 1 онбординга или главное меню."""
    lang = callback.data.split(":")[-1]
    if lang not in _SUPPORTED_LANGS:
        lang = "ru"

    logger.info("lang_selected: tid=%s lang=%s", user.telegram_id, lang)

    # Сохраняем язык в DB + Redis
    await save_user_lang(session, user.id, user.telegram_id, lang)

    # Если онбординг уже пройден — сразу главное меню
    from bot.handlers.onboarding import is_onboarding_done
    onboarding_done = await is_onboarding_done(session, user.id)

    if onboarding_done:
        from bot.keyboards.main import main_menu
        from bot.keyboards.reply import main_reply_keyboard
        from bot.handlers.start import _welcome_text
        from bot.services.menu_tracker import clear_keyboard_shown, mark_keyboard_shown
        from bot.utils import safe_answer_menu
        name = callback.from_user.first_name or None
        # Сбрасываем флаг и всегда переотправляем reply-клавиатуру при выборе языка
        await clear_keyboard_shown(user.telegram_id)
        await safe_answer_menu(callback.message, "🌙", reply_markup=main_reply_keyboard(lang), parse_mode=None)
        await mark_keyboard_shown(user.telegram_id)
        await callback.message.edit_text(
            _welcome_text(name, lang),
            reply_markup=main_menu(lang),
            parse_mode="Markdown",
        )
    else:
        # Показываем онбординг экран 1 в выбранном языке
        from bot.handlers.onboarding import _screen1_kb
        await callback.message.edit_text(
            t("ob_screen1", lang),
            reply_markup=_screen1_kb(lang),
            parse_mode="Markdown",
        )
    await callback.answer()
