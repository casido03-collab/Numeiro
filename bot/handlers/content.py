"""Контентная система — раздел «Интересное»."""
import asyncio
import logging
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.models.user import User
from bot.services.cache import get_redis

router = Router()
logger = logging.getLogger(__name__)


# ─── Статьи ───────────────────────────────────────────────────────────────────

ARTICLES = {
    "numerology": {
        "title": "🔮 Тайны нумерологии",
        "text": (
            "✨ *Иногда кажется, что определённые числа буквально преследуют нас.*\n\n"
            "11:11 на часах. Повторяющиеся даты. Странные совпадения.\n\n"
            "В нумерологии считается, что числа — это не просто математика, "
            "а отражение внутренних процессов человека.\n\n"
            "Каждое число несёт собственную энергетику:\n"
            "• *1* — начало и лидерство\n"
            "• *7* — интуиция и поиск смысла\n"
            "• *9* — завершение циклов\n\n"
            "Многие люди начинают замечать повторяющиеся числа именно в периоды перемен, "
            "эмоциональных переживаний или важных решений.\n\n"
            "✨ _Возможно, ваше число судьбы уже пытается подсказать вам направление._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="🔮 Рассчитать число судьбы", callback_data="menu:reading")],
            [InlineKeyboardButton(text="🌙 Получить прогноз", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:numerology")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "astrology": {
        "title": "🌙 Астрология дня",
        "text": (
            "🌙 *Вы замечали, как в некоторые дни всё буквально валится из рук?*\n\n"
            "А иногда наоборот — энергия словно подталкивает к действиям.\n\n"
            "Астрология связывает это с положением планет и Луны.\n\n"
            "Например:\n"
            "• *Полнолуние* часто усиливает эмоции\n"
            "• *Ретроградные периоды* создают ощущение задержек и хаоса\n\n"
            "Даже люди, которые не верят в астрологию, нередко замечают изменение "
            "настроения в определённые периоды.\n\n"
            "✨ _Возможно, сегодня именно тот день, когда стоит прислушаться к себе внимательнее._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="🌙 Получить прогноз", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="✨ Энергия дня", callback_data="menu:daily")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:astrology")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "compatibility": {
        "title": "❤️ Совместимость пар",
        "text": (
            "❤️ *Некоторые люди появляются в нашей жизни словно не случайно.*\n\n"
            "С кем-то связь возникает мгновенно.\n"
            "А с кем-то отношения становятся эмоционально тяжёлыми и запутанными.\n\n"
            "В эзотерических практиках считается, что между людьми может существовать "
            "энергетическая совместимость.\n\n"
            "Иногда партнёры усиливают друг друга.\n"
            "А иногда — запускают внутренние конфликты и уроки.\n\n"
            "Именно поэтому некоторые отношения ощущаются как судьбоносные.\n\n"
            "✨ _Возможно, ваша связь тоже скрывает более глубокий смысл._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="❤️ Проверить совместимость", callback_data="compat:start")],
            [InlineKeyboardButton(text="🔮 Задать вопрос", callback_data="menu:question")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:compatibility")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "tarot": {
        "title": "🃏 Секреты Таро",
        "text": (
            "🃏 *Карты Таро уже много веков используются как инструмент символов и подсознания.*\n\n"
            "Иногда один расклад способен удивительно точно описать внутреннее состояние человека.\n\n"
            "Таро не предсказывает будущее буквально.\n"
            "Скорее оно помогает увидеть:\n"
            "• скрытые эмоции\n"
            "• внутренние страхи\n"
            "• вероятные сценарии\n"
            "• подсказки для принятия решений\n\n"
            "Именно поэтому многие люди чувствуют странное совпадение между картами и "
            "событиями своей жизни.\n\n"
            "✨ _Возможно, ответы уже находятся внутри вас._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="🃏 Сделать расклад", callback_data="menu:reading")],
            [InlineKeyboardButton(text="🌙 Прогноз недели", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:tarot")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "energy": {
        "title": "✨ Энергия человека",
        "text": (
            "✨ *У каждого человека есть собственная энергетика.*\n\n"
            "Некоторые люди буквально заряжают нас энергией.\n"
            "А после общения с другими появляется усталость и эмоциональная тяжесть.\n\n"
            "В эзотерике считается, что внутреннее состояние человека напрямую связано:\n"
            "• с эмоциями\n"
            "• окружением\n"
            "• мыслями\n"
            "• жизненными циклами\n\n"
            "Иногда смена энергетики ощущается ещё до того, как происходят реальные события.\n\n"
            "✨ _Возможно, сейчас вы входите в новый жизненный этап._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="✨ Узнать свою энергетику", callback_data="menu:reading")],
            [InlineKeyboardButton(text="🔮 Матрица судьбы", callback_data="matrix:start")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:energy")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "destiny": {
        "title": "🌌 Судьба и знаки",
        "text": (
            "🌌 *Многие люди замечают странные совпадения:*\n\n"
            "• одинаковые числа\n"
            "• повторяющиеся ситуации\n"
            "• случайные встречи\n"
            "• неожиданные знаки\n\n"
            "Иногда кажется, будто жизнь пытается обратить наше внимание на что-то важное.\n\n"
            "В эзотерике подобные события называют знаками судьбы.\n\n"
            "Особенно часто они появляются в периоды:\n"
            "• внутренних перемен\n"
            "• сильных эмоций\n"
            "• важных решений\n\n"
            "✨ _Возможно, некоторые события в вашей жизни уже несут скрытый смысл._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="🌌 Получить знак дня", callback_data="menu:daily")],
            [InlineKeyboardButton(text="🔮 Личный вопрос", callback_data="menu:question")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:destiny")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
    "why": {
        "title": "🧠 Почему это работает?",
        "text": (
            "🧠 *Даже люди, которые относятся к эзотерике скептически,*\n"
            "часто замечают странное чувство узнавания.\n\n"
            "Почему некоторые расклады кажутся настолько точными?\n\n"
            "Частично это связано с тем, что человек начинает глубже анализировать "
            "себя и собственные эмоции.\n\n"
            "Эзотерические практики часто работают как способ:\n"
            "• обратить внимание на внутренние переживания\n"
            "• замедлиться\n"
            "• посмотреть на ситуацию под другим углом\n\n"
            "Иногда именно это помогает человеку принять важное решение.\n\n"
            "✨ _Возможно, ответы находятся ближе, чем кажется._"
        ),
        "buttons": [
            [InlineKeyboardButton(text="🔮 Попробовать на себе", callback_data="menu:reading")],
            [InlineKeyboardButton(text="🌙 Получить прогноз", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="📤 Поделиться", callback_data="share:content:why")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ],
    },
}

ARTICLE_BUTTON_LABELS = {
    "numerology":    "🔮 Тайны нумерологии",
    "astrology":     "🌙 Астрология дня",
    "compatibility": "❤️ Совместимость пар",
    "tarot":         "🃏 Секреты Таро",
    "energy":        "✨ Энергия человека",
    "destiny":       "🌌 Судьба и знаки",
    "why":           "🧠 Почему это работает?",
}


# ─── Трекинг просмотров ────────────────────────────────────────────────────────

async def track_view(article_key: str):
    try:
        r = await get_redis()
        today = date.today().isoformat()
        await r.incr(f"content:views:{today}:{article_key}")
    except Exception as e:
        logger.debug("Content view tracking failed: %s", e)


async def get_popular_today() -> list[tuple[str, int]]:
    """Return top-3 articles by view count today."""
    try:
        r = await get_redis()
        today = date.today().isoformat()
        counts = []
        for key in ARTICLES:
            n = await r.get(f"content:views:{today}:{key}")
            counts.append((key, int(n) if n else 0))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:3]
    except Exception:
        return [("numerology", 0), ("compatibility", 0), ("astrology", 0)]


# ─── Клавиатуры ────────────────────────────────────────────────────────────────

def content_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Тайны нумерологии", callback_data="content:numerology")],
        [InlineKeyboardButton(text="🌙 Астрология дня", callback_data="content:astrology")],
        [
            InlineKeyboardButton(text="❤️ Совместимость пар", callback_data="content:compatibility"),
            InlineKeyboardButton(text="🃏 Секреты Таро", callback_data="content:tarot"),
        ],
        [
            InlineKeyboardButton(text="✨ Энергия человека", callback_data="content:energy"),
            InlineKeyboardButton(text="🌌 Судьба и знаки", callback_data="content:destiny"),
        ],
        [InlineKeyboardButton(text="🧠 Почему это работает?", callback_data="content:why")],
        [InlineKeyboardButton(text="🔥 Популярное сегодня", callback_data="content:popular")],
    ])


# ─── Обработчики reply-кнопки ─────────────────────────────────────────────────

@router.message(F.text == "📚 Интересное")
async def reply_interesting(message: Message, state: FSMContext):
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    try:
        await asyncio.wait_for(message.delete(), timeout=5.0)
    except Exception:
        pass
    from bot.utils import show_menu_message
    await show_menu_message(
        message, message.from_user.id,
        "✨ *Выберите тему, которая вам интересна:*",
        content_menu_kb(),
    )


@router.message(F.text == "🔮 Меню")
async def reply_menu(message: Message, user: User, state: FSMContext):
    """Кнопка «🔮 Меню» работает как /start — полный welcome-экран + клавиатура."""
    try:
        await asyncio.wait_for(state.clear(), timeout=3.0)
    except Exception:
        pass
    try:
        await asyncio.wait_for(message.delete(), timeout=5.0)
    except Exception:
        pass
    from bot.keyboards.main import main_menu
    from bot.keyboards.reply import main_reply_keyboard
    from bot.handlers.start import _welcome_text
    from bot.services.menu_tracker import mark_keyboard_shown
    from bot.utils import show_menu_message

    name = user.first_name or None
    # Отправляем клавиатуру (как /start — всегда, чтобы она точно была видна)
    from bot.utils import safe_answer
    sent = await safe_answer(message, "🌙", reply_markup=main_reply_keyboard(), parse_mode=None)
    if sent:
        await mark_keyboard_shown(user.telegram_id)
    # Полный welcome-текст + inline меню
    await show_menu_message(
        message, user.telegram_id,
        _welcome_text(name),
        main_menu(),
        force_new=True,
    )


# ─── Обработчик inline-меню контента ─────────────────────────────────────────

@router.callback_query(F.data == "content:menu")
async def show_content_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "✨ *Выберите тему, которая вам интересна:*",
        reply_markup=content_menu_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:") & ~F.data.startswith("content:popular"))
async def show_article(callback: CallbackQuery):
    article_key = callback.data.split(":")[-1]
    if article_key == "menu":
        return  # обработан выше

    article = ARTICLES.get(article_key)
    if not article:
        await callback.answer("Статья не найдена")
        return

    await track_view(article_key)

    kb = InlineKeyboardMarkup(inline_keyboard=article["buttons"])
    from bot.utils import safe_edit
    await safe_edit(callback.message, article["text"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "content:popular")
async def show_popular(callback: CallbackQuery):
    popular = await get_popular_today()

    lines = []
    for key, count in popular:
        label = ARTICLE_BUTTON_LABELS.get(key, key)
        lines.append(f"• {label}")

    if not any(count > 0 for _, count in popular):
        # Нет данных — показать дефолтный список
        text = (
            "🔥 *Сегодня чаще всего пользователи читают:*\n\n"
            "• ❤️ Совместимость после расставания\n"
            "• 🌙 Прогноз на ближайшие 7 дней\n"
            "• 👁 Значение числа 11:11"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Открыть совместимость", callback_data="compat:start")],
            [InlineKeyboardButton(text="🌙 Получить прогноз", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="🔮 Тайны нумерологии", callback_data="content:numerology")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")],
        ])
    else:
        text = "🔥 *Популярное сегодня:*\n\n" + "\n".join(lines)
        buttons = [
            [InlineKeyboardButton(text=ARTICLE_BUTTON_LABELS.get(k, k), callback_data=f"content:{k}")]
            for k, _ in popular
        ]
        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="content:menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Share контента ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("share:content:"))
async def share_content(callback: CallbackQuery, user: User):
    await callback.answer()  # сразу, до async-работы

    try:
        article_key = callback.data.split(":")[-1]
        article = ARTICLES.get(article_key)
        if not article:
            return

        import html as _html
        from bot.handlers.share import _get_bot_username
        bot_username = await _get_bot_username(callback.bot)
        bot_link = f"https://t.me/{bot_username}"
        ref_link = f"{bot_link}?start=ref_{user.telegram_id}"

        await callback.message.answer(
            f"📤 <b>Поделись с друзьями:</b>\n\n"
            f"<i>{_html.escape(article['title'])}</i>\n\n"
            f'Читай эзотерические разборы в боте <a href="{bot_link}">Aisha AI 🔮</a>\n\n'
            f"👉 {ref_link}",
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except Exception:
        pass


# ─── Контентные CTA после действий ───────────────────────────────────────────

def compatibility_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❤️ Что такое кармические отношения?",
            callback_data="content:compatibility",
        )],
    ])


def weekly_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌙 Как Луна влияет на настроение?",
            callback_data="content:astrology",
        )],
    ])


def reading_cta_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👁 Тайна 11:11",
            callback_data="content:numerology",
        )],
    ])
