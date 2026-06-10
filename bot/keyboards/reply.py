"""Reply keyboard — постоянная нижняя панель."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Тексты кнопок на всех языках
REPLY_LABELS: dict[str, dict[str, str]] = {
    "menu": {
        "ru": "🔮 Меню",
        "en": "🔮 Menu",
        "fa": "🔮 منو",
        "tr": "🔮 Menü",
    },
    "interesting": {
        "ru": "📚 Интересное",
        "en": "📚 Interesting",
        "fa": "📚 جالب",
        "tr": "📚 İlginç",
    },
    "friends": {
        "ru": "👥 Друзья",
        "en": "👥 Friends",
        "fa": "👥 دوستان",
        "tr": "👥 Arkadaşlar",
    },
    "plans": {
        "ru": "💎 Подписка",
        "en": "💎 Plans",
        "fa": "💎 اشتراک",
        "tr": "💎 Abonelik",
    },
}

# Все возможные тексты кнопок (для фильтров-исключений)
ALL_REPLY_TEXTS: set[str] = {
    text for btn in REPLY_LABELS.values() for text in btn.values()
}

# Тексты для каждой кнопки (для конкретных обработчиков)
MENU_TEXTS: set[str] = set(REPLY_LABELS["menu"].values())
INTERESTING_TEXTS: set[str] = set(REPLY_LABELS["interesting"].values())
FRIENDS_TEXTS: set[str] = set(REPLY_LABELS["friends"].values())
PLANS_TEXTS: set[str] = set(REPLY_LABELS["plans"].values())


def main_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Постоянная панель на языке пользователя."""
    _lang = lang if lang in ("ru", "en", "fa", "tr") else "en"
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=REPLY_LABELS["menu"][_lang]),
                KeyboardButton(text=REPLY_LABELS["interesting"][_lang]),
            ],
            [
                KeyboardButton(text=REPLY_LABELS["friends"][_lang]),
                KeyboardButton(text=REPLY_LABELS["plans"][_lang]),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
