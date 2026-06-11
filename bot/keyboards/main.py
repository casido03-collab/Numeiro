from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.i18n.translations import t


# ─── Главное меню ──────────────────────────────────────────────────────────────

def main_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("menu_horoscope", lang),     callback_data="menu:horoscope"),
            InlineKeyboardButton(text=t("menu_tarot", lang),         callback_data="menu:tarot"),
        ],
        [
            InlineKeyboardButton(text=t("menu_daily", lang),         callback_data="menu:daily"),
            InlineKeyboardButton(text=t("menu_reading", lang),       callback_data="menu:reading"),
        ],
        [InlineKeyboardButton(text=t("menu_matrix", lang),           callback_data="matrix:start")],
        [InlineKeyboardButton(text=t("menu_weekly", lang),           callback_data="menu:weekly")],
        [InlineKeyboardButton(text=t("menu_compatibility", lang),    callback_data="menu:compatibility")],
        [InlineKeyboardButton(text=t("menu_question", lang),         callback_data="menu:question")],
        [InlineKeyboardButton(text=t("menu_dates", lang),            callback_data="menu:dates")],
        [InlineKeyboardButton(text=t("menu_reviews", lang),          url="https://t.me/ezoterika_aisha")],
        [
            InlineKeyboardButton(text=t("menu_plans", lang),         callback_data="menu:plans"),
            InlineKeyboardButton(text=t("menu_history", lang),       callback_data="reports:menu"),
        ],
    ])


# ─── Сферы ─────────────────────────────────────────────────────────────────────

def sphere_menu(prefix: str, back: str = "menu:main") -> InlineKeyboardMarkup:
    spheres = [
        ("❤️ Любовь",              "love"),
        ("💰 Деньги",              "money"),
        ("💼 Работа",              "work"),
        ("⚡ Здоровье / Энергия",  "health"),
        ("👨‍👩‍👧 Семья",              "family"),
        ("🎯 Важное решение",      "decision"),
        ("🔮 Общий прогноз",       "general"),
        ("🌟 Предназначение",      "purpose"),
        ("🧠 Личностный рост",     "growth"),
        ("💑 Партнёрство",         "partnership"),
        ("👶 Дети",                "children"),
        ("🎓 Образование",         "education"),
        ("✈️ Переезд / Поездка",   "relocation"),
        ("🏠 Жильё / Дом",         "home"),
        ("🌿 Духовность",          "spiritual"),
        ("🎨 Творчество",          "creativity"),
        ("🤝 Дружба",              "friendship"),
        ("🔥 Мотивация",           "motivation"),
        ("🧘 Внутренний мир",      "inner_peace"),
        ("💫 Карма",               "karma"),
        ("🚀 Карьерный рост",      "career"),
    ]
    # Два столбца
    btns = [InlineKeyboardButton(text=name, callback_data=f"{prefix}:{key}") for name, key in spheres]
    buttons = [btns[i:i+2] for i in range(0, len(btns), 2)]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Совместимость ─────────────────────────────────────────────────────────────

def relation_type_menu() -> InlineKeyboardMarkup:
    types = [
        ("❤️ Романтика", "love"),
        ("💍 Брак", "marriage"),
        ("🤝 Дружба", "friendship"),
        ("💼 Работа", "work"),
        ("🔄 Бывший партнёр", "ex"),
        ("💫 Потенциальный партнёр", "potential"),
    ]
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"compat:type:{key}")] for name, key in types]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="compat:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Подбор дат ────────────────────────────────────────────────────────────────

def event_type_menu() -> InlineKeyboardMarkup:
    events = [
        ("🚀 Запуск проекта",        "project_launch"),
        ("💍 Свадьба",               "wedding"),
        ("🛍 Важная покупка",        "purchase"),
        ("🏠 Переезд",               "move"),
        ("🗣 Важный разговор",       "conversation"),
        ("✈️ Поездка",               "travel"),
        ("💼 Собеседование",         "interview"),
        ("🤝 Деловая встреча",       "business_meeting"),
        ("📝 Подписание договора",   "contract"),
        ("🎓 Начало обучения",       "education"),
        ("💰 Крупная инвестиция",    "investment"),
        ("🏥 Медицинская процедура", "medical"),
        ("🎨 Творческий проект",     "creative"),
        ("🙏 Духовная практика",     "spiritual"),
    ]
    # Два столбца: берём пары событий в одну строку
    btns = [InlineKeyboardButton(text=name, callback_data=f"dates:event:{key}") for name, key in events]
    buttons = [btns[i:i+2] for i in range(0, len(btns), 2)]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Тарифы ────────────────────────────────────────────────────────────────────

def plans_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("plan_btn_lite", lang),    callback_data="buy:plan:lite")],
        [InlineKeyboardButton(text=t("plan_btn_premium", lang), callback_data="buy:plan:premium")],
        [InlineKeyboardButton(text=t("plan_btn_pro", lang),     callback_data="buy:plan:pro")],
        [InlineKeyboardButton(text=t("plan_btn_oneoff", lang),  callback_data="buy:oneoff")],
        [InlineKeyboardButton(text=t("btn_back", lang),         callback_data="menu:main")],
    ])


def one_time_products_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("product_btn_matrix", lang),   callback_data="buy:product:full_matrix")],
        [InlineKeyboardButton(text=t("product_btn_compat", lang),   callback_data="buy:product:compatibility")],
        [InlineKeyboardButton(text=t("product_btn_weekly", lang),   callback_data="buy:product:weekly_report")],
        [InlineKeyboardButton(text=t("product_btn_question", lang), callback_data="buy:product:personal_question")],
        [InlineKeyboardButton(text=t("product_btn_dates", lang),    callback_data="buy:product:date_selection")],
        [InlineKeyboardButton(text=t("btn_back_to_plans", lang),    callback_data="menu:plans")],
    ])


def payment_method_keyboard(
    product_type: str,
    product_key: str,
    stars: int,
    back: str = "menu:plans",
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Выбор способа оплаты — только Telegram Stars."""
    buttons = [
        [InlineKeyboardButton(
            text=t("pay_btn_stars", lang).format(stars=stars),
            callback_data=f"pay:stars:{product_type}:{product_key}",
        )],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data=back)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── После ответа ──────────────────────────────────────────────────────────────

def upsell_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Получить полный разбор", callback_data="matrix:start")],
        [InlineKeyboardButton(text="💞 Совместимость", callback_data="compat:start")],
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data="weekly:start")],
        [InlineKeyboardButton(text="📜 Посмотреть тарифы", callback_data="menu:plans")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_reading_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить разбор", callback_data="matrix:start")],
        [InlineKeyboardButton(text="🔮 Задать вопрос Бабушке Aisha", callback_data="menu:question")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_question_keyboard_free() -> InlineKeyboardMarkup:
    """Клавиатура после ответа на вопрос для бесплатных пользователей."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Получить глубокий расклад", callback_data="cabinet:open")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_question_keyboard_paid() -> InlineKeyboardMarkup:
    """Клавиатура после ответа на вопрос для платных пользователей."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Задать ещё вопрос", callback_data="menu:question")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


# Версии клавиатур с CTA-кнопкой — избегают лишнего API-вызова (отдельного сообщения)

def upsell_keyboard_reading() -> InlineKeyboardMarkup:
    """upsell_keyboard + кнопка контентного CTA для мини-разбора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Получить полный разбор", callback_data="matrix:start")],
        [InlineKeyboardButton(text="💞 Совместимость", callback_data="compat:start")],
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data="weekly:start")],
        [InlineKeyboardButton(text="👁 Тайна 11:11", callback_data="content:numerology")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_reading_keyboard_matrix() -> InlineKeyboardMarkup:
    """after_reading_keyboard + кнопка контентного CTA для матрицы."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Другой разбор", callback_data="menu:reading")],
        [InlineKeyboardButton(text="🔮 Задать вопрос Бабушке Aisha", callback_data="menu:question")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="👁 Тайна 11:11", callback_data="content:numerology")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_reading_keyboard_weekly() -> InlineKeyboardMarkup:
    """after_reading_keyboard + кнопка контентного CTA для недельного прогноза."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить разбор", callback_data="matrix:start")],
        [InlineKeyboardButton(text="🔮 Задать вопрос Бабушке Aisha", callback_data="menu:question")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="🌙 Как Луна влияет на настроение?", callback_data="content:astrology")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_tarot_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после показа карты дня."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Расшифровать глубже", callback_data="menu:question")],
        [InlineKeyboardButton(text="🔮 Задать вопрос Бабушке Aisha", callback_data="menu:question")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
    ])


def limit_reached_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Открыть больше возможностей", callback_data="menu:plans")],
        [InlineKeyboardButton(text="📜 Посмотреть тарифы", callback_data="menu:plans")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


# ─── Вспомогательные ───────────────────────────────────────────────────────────

def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")]
    ])


def back_to_plans() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К тарифам", callback_data="menu:plans")]
    ])


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨 Мужской", callback_data="profile:gender:male"),
            InlineKeyboardButton(text="👩 Женский", callback_data="profile:gender:female"),
        ],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="profile:gender:unknown")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="profile:cancel")],
    ])


def cancel_fsm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="profile:cancel")]
    ])
