from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ─── Главное меню ──────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Энергия дня", callback_data="menu:daily")],
        [InlineKeyboardButton(text="✨ Мой разбор", callback_data="menu:reading")],
        [InlineKeyboardButton(text="🌟 Полная матрица судьбы", callback_data="matrix:start")],
        [InlineKeyboardButton(text="📅 Расклад на неделю", callback_data="menu:weekly")],
        [InlineKeyboardButton(text="💞 Совместимость", callback_data="menu:compatibility")],
        [InlineKeyboardButton(text="🔮 Задать вопрос Тарологу", callback_data="menu:question")],
        [InlineKeyboardButton(text="📆 Подбор дат", callback_data="menu:dates")],
        [
            InlineKeyboardButton(text="📜 Тарифы", callback_data="menu:plans"),
            InlineKeyboardButton(text="🌀 История", callback_data="reports:menu"),
        ],
    ])


# ─── Сферы ─────────────────────────────────────────────────────────────────────

def sphere_menu(prefix: str, back: str = "menu:main") -> InlineKeyboardMarkup:
    spheres = [
        ("❤️ Любовь", "love"),
        ("💰 Деньги", "money"),
        ("💼 Работа", "work"),
        ("⚡ Здоровье / Энергия", "health"),
        ("👨‍👩‍👧 Семья", "family"),
        ("🎯 Важное решение", "decision"),
        ("🔮 Общий прогноз", "general"),
    ]
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"{prefix}:{key}")] for name, key in spheres]
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
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"dates:event:{key}")] for name, key in events]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Тарифы ────────────────────────────────────────────────────────────────────

def plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💫 Lite — 299 ₽ / 7 дней", callback_data="buy:plan:lite")],
        [InlineKeyboardButton(text="🌟 Premium — 999 ₽ / месяц", callback_data="buy:plan:premium")],
        [InlineKeyboardButton(text="🔥 Pro — 1 499 ₽ / месяц", callback_data="buy:plan:pro")],
        [InlineKeyboardButton(text="💎 Разовые покупки", callback_data="buy:oneoff")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
    ])


def one_time_products_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Матрица судьбы — 299 ₽", callback_data="buy:product:full_matrix")],
        [InlineKeyboardButton(text="💞 Совместимость — 199 ₽", callback_data="buy:product:compatibility")],
        [InlineKeyboardButton(text="📅 Расклад на неделю — 199 ₽", callback_data="buy:product:weekly_report")],
        [InlineKeyboardButton(text="❓ Личный вопрос — 99 ₽", callback_data="buy:product:personal_question")],
        [InlineKeyboardButton(text="📆 Подбор дат — 199 ₽", callback_data="buy:product:date_selection")],
        [InlineKeyboardButton(text="◀️ Назад к тарифам", callback_data="menu:plans")],
    ])


def payment_method_keyboard(product_type: str, product_key: str, stars: int, back: str = "menu:plans") -> InlineKeyboardMarkup:
    """product_type: 'plan' or 'product'"""
    yk = f"pay:yookassa:{product_type}:{product_key}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Банковская карта", callback_data=yk)],
        [InlineKeyboardButton(text="🏦 СБП", callback_data=yk)],
        [InlineKeyboardButton(text="🟢 SberPay", callback_data=yk)],
        [InlineKeyboardButton(text="🟡 ЮMoney", callback_data=yk)],
        [InlineKeyboardButton(
            text=f"⭐ Telegram Stars ({stars})",
            callback_data=f"pay:stars:{product_type}:{product_key}",
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back)],
    ])


def card_methods_keyboard(product_type: str, product_key: str) -> InlineKeyboardMarkup:
    """Выбор конкретной платёжной системы картой."""
    back_cb = f"buy:{product_type}:{product_key}" if product_type == "plan" else "buy:oneoff"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 СБП (быстрый платёж)", callback_data=f"pay:sbp:{product_type}:{product_key}")],
        [InlineKeyboardButton(text="💳 Visa / MasterCard", callback_data=f"pay:card_visa:{product_type}:{product_key}")],
        [InlineKeyboardButton(text="🟡 ЮMoney", callback_data=f"pay:ymoney:{product_type}:{product_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"pay:method:{product_type}:{product_key}")],
    ])


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
        [InlineKeyboardButton(text="🌊 Спросить ещё глубже", url="https://t.me/m/-Ekcn86bNmU0")],
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
        [InlineKeyboardButton(text="🌊 Спросить ещё глубже", url="https://t.me/m/-Ekcn86bNmU0")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="👁 Тайна 11:11", callback_data="content:numerology")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])


def after_reading_keyboard_weekly() -> InlineKeyboardMarkup:
    """after_reading_keyboard + кнопка контентного CTA для недельного прогноза."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить разбор", callback_data="matrix:start")],
        [InlineKeyboardButton(text="🌊 Спросить ещё глубже", url="https://t.me/m/-Ekcn86bNmU0")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:reading")],
        [InlineKeyboardButton(text="🌙 Как Луна влияет на настроение?", callback_data="content:astrology")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
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
