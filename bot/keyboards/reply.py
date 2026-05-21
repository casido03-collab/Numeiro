"""Reply keyboard — постоянная нижняя панель."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Постоянная панель: Меню | Интересное | Друзья | Подписка."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔮 Меню"),
                KeyboardButton(text="📚 Интересное"),
            ],
            [
                KeyboardButton(text="👥 Друзья"),
                KeyboardButton(text="💎 Подписка"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
