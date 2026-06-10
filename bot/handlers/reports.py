"""Раздел «🌀 Мои Разборы» — история разборов пользователя."""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.reports_service import (
    get_user_reports,
    count_reports,
    get_report_by_id,
    get_categories_with_counts,
    FREE_LIMIT,
    PAGE_SIZE,
)
from bot.services.limits import get_user_plan
from bot.utils import safe_edit

router = Router()
logger = logging.getLogger(__name__)

# ─── Конфиг ───────────────────────────────────────────────────────────────────

_REPORT_TYPE_LABELS: dict[str, dict[str, str]] = {
    "horoscope":         {"ru": "🔯 Гороскоп дня",      "en": "🔯 Daily Horoscope",   "fa": "🔯 طالع‌بینی روز",   "tr": "🔯 Günlük Burç"},
    "tarot_card":        {"ru": "🃏 Карты дня",          "en": "🃏 Cards of the Day",  "fa": "🃏 کارت‌های روز",    "tr": "🃏 Günün Kartları"},
    "weekly_forecast":   {"ru": "📅 Прогнозы",           "en": "📅 Forecasts",         "fa": "📅 پیش‌بینی‌ها",     "tr": "📅 Tahminler"},
    "compatibility":     {"ru": "💞 Совместимости",      "en": "💞 Compatibilities",   "fa": "💞 سازگاری‌ها",      "tr": "💞 Uyumluluklar"},
    "personal_question": {"ru": "🔮 Личные вопросы",     "en": "🔮 Personal Questions","fa": "🔮 سؤالات شخصی",     "tr": "🔮 Kişisel Sorular"},
    "destiny_matrix":    {"ru": "🌟 Матрица судьбы",     "en": "🌟 Destiny Matrix",    "fa": "🌟 ماتریس سرنوشت",   "tr": "🌟 Kader Matrisi"},
    "daily_energy":      {"ru": "⚡ Энергия дня",        "en": "⚡ Daily Energy",       "fa": "⚡ انرژی روز",        "tr": "⚡ Günün Enerjisi"},
    "date_selection":    {"ru": "📆 Подбор дат",         "en": "📆 Date Selection",    "fa": "📆 انتخاب تاریخ",    "tr": "📆 Tarih Seçimi"},
    "mini_report":       {"ru": "✨ Мини-разборы",        "en": "✨ Mini Readings",      "fa": "✨ تفسیرهای کوتاه",  "tr": "✨ Mini Okumalar"},
}


def _label(report_type: str, lang: str = "ru") -> str:
    entry = _REPORT_TYPE_LABELS.get(report_type)
    if not entry:
        return report_type
    return entry.get(lang) or entry.get("en") or report_type


# Keep old name for backward compatibility (used in reports_service etc.)
REPORT_TYPE_LABELS: dict[str, str] = {k: v["ru"] for k, v in _REPORT_TYPE_LABELS.items()}

CATEGORY_ORDER = [
    "horoscope",
    "tarot_card",
    "weekly_forecast",
    "compatibility",
    "personal_question",
    "destiny_matrix",
    "daily_energy",
    "date_selection",
    "mini_report",
]

_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]


def _truncate(text: str, limit: int = 3600, lang: str = "ru") -> str:
    if len(text) <= limit:
        return text
    _cut = {"ru": "… текст обрезан", "en": "… text truncated", "fa": "… متن کوتاه شد", "tr": "… metin kısaltıldı"}.get(lang, "… text truncated")
    return text[:limit].rsplit(" ", 1)[0] + f"\n\n_{_cut}_"


# ─── Главный экран раздела ────────────────────────────────────────────────────

@router.callback_query(F.data == "reports:menu")
async def my_reports_menu(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    counts = await get_categories_with_counts(session, user.id)

    _main_menu  = {"ru": "🔙 Главное меню",             "en": "🔙 Main menu",               "fa": "🔙 منوی اصلی",        "tr": "🔙 Ana menü"}.get(lang, "🔙 Main menu")
    _get_fore   = {"ru": "📅 Получить прогноз",          "en": "📅 Get forecast",            "fa": "📅 دریافت پیش‌بینی",  "tr": "📅 Tahmin al"}.get(lang, "📅 Get forecast")
    _check_comp = {"ru": "💞 Проверить совместимость",   "en": "💞 Check compatibility",     "fa": "💞 بررسی سازگاری",   "tr": "💞 Uyum kontrol"}.get(lang, "💞 Check compatibility")

    if not counts:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_get_fore, callback_data="menu:weekly")],
            [InlineKeyboardButton(text=_check_comp, callback_data="compat:start")],
            [InlineKeyboardButton(text=_main_menu, callback_data="menu:main")],
        ])
        _empty = {
            "ru": "🌀 *У вас пока нет сохранённых разборов.*\n\nНачните с первого прогноза или совместимости — и они появятся здесь.",
            "en": "🌀 *You have no saved readings yet.*\n\nStart with your first forecast or compatibility check — they will appear here.",
            "fa": "🌀 *هنوز هیچ تفسیر ذخیره‌شده‌ای ندارید.*\n\nبا اولین پیش‌بینی یا بررسی سازگاری شروع کنید — اینجا ظاهر می‌شوند.",
            "tr": "🌀 *Henüz kayıtlı okumanız yok.*\n\nİlk tahmininiz veya uyumluluk kontrolünüzle başlayın — burada görünecekler.",
        }.get(lang, "🌀 *You have no saved readings yet.*\n\nStart with your first forecast or compatibility check — they will appear here.")
        await callback.message.edit_text(_empty, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
        return

    lines: list[str] = []
    buttons: list[list[InlineKeyboardButton]] = []

    for rtype in CATEGORY_ORDER:
        cnt = counts.get(rtype, 0)
        if cnt == 0:
            continue
        lbl = _label(rtype, lang)
        lines.append(f"{lbl} — {cnt}")
        buttons.append([InlineKeyboardButton(
            text=f"{lbl} ({cnt})",
            callback_data=f"reports:cat:{rtype}:0",
        )])

    buttons.append([InlineKeyboardButton(text=_main_menu, callback_data="menu:main")])

    _title = {"ru": "🌀 *Ваши разборы*",        "en": "🌀 *Your Readings*",       "fa": "🌀 *تفسیرهای شما*",       "tr": "🌀 *Okumalarınız*"}.get(lang, "🌀 *Your Readings*")
    _desc  = {"ru": "Здесь сохраняются ваши прогнозы, совместимости и личные ответы.\nВы можете вернуться к ним в любой момент.",
              "en": "Your forecasts, compatibilities and personal answers are saved here.\nYou can return to them at any time.",
              "fa": "پیش‌بینی‌ها، سازگاری‌ها و پاسخ‌های شخصی شما اینجا ذخیره می‌شوند.\nمی‌توانید هر زمان به آن‌ها برگردید.",
              "tr": "Tahminleriniz, uyumluluk sonuçlarınız ve kişisel yanıtlarınız burada kaydedilir.\nİstediğiniz zaman geri dönebilirsiniz."}.get(lang, "Your readings are saved here.")

    text = f"{_title}\n\n{_desc}\n\n" + "\n".join(lines)
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Список по категории ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:cat:"))
async def reports_category(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    parts = callback.data.split(":")          # ['reports', 'cat', type, page]
    if len(parts) < 4:
        await callback.answer()
        return

    report_type = parts[2]
    try:
        page = int(parts[3])
    except ValueError:
        page = 0

    plan = await get_user_plan(session, user.id)
    is_paid = plan in ("lite", "premium", "pro")
    limit = PAGE_SIZE if is_paid else FREE_LIMIT
    offset = page * PAGE_SIZE if is_paid else 0

    total = await count_reports(session, user.id, report_type)
    reports = await get_user_reports(session, user.id, report_type, limit=limit, offset=offset)
    lbl = _label(report_type, lang)

    _back      = {"ru": "◀️ Назад",       "en": "◀️ Back",       "fa": "◀️ بازگشت",    "tr": "◀️ Geri"}.get(lang, "◀️ Back")
    _main_menu = {"ru": "🔙 Главное меню", "en": "🔙 Main menu",  "fa": "🔙 منوی اصلی", "tr": "🔙 Ana menü"}.get(lang, "🔙 Main menu")
    _open      = {"ru": "Открыть",        "en": "Open",          "fa": "باز کردن",     "tr": "Aç"}.get(lang, "Open")
    _prev      = {"ru": "⬅️ Назад",       "en": "⬅️ Prev",       "fa": "⬅️ قبلی",      "tr": "⬅️ Önceki"}.get(lang, "⬅️ Prev")
    _next      = {"ru": "➡️ Ещё",         "en": "➡️ More",       "fa": "➡️ بیشتر",     "tr": "➡️ Daha"}.get(lang, "➡️ More")

    if not reports:
        _empty = {"ru": "_Разборов этого типа пока нет._", "en": "_No readings of this type yet._",
                  "fa": "_هنوز هیچ تفسیری از این نوع وجود ندارد._", "tr": "_Bu türde henüz okuma yok._"}.get(lang, "_No readings of this type yet._")
        await callback.message.edit_text(
            f"{lbl}\n\n{_empty}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=_back, callback_data="reports:menu")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # Список строк
    lines = [f"*{lbl}*\n"]
    item_buttons: list[list[InlineKeyboardButton]] = []
    for i, r in enumerate(reports):
        num = offset + i + 1
        icon = _NUMBERS[i] if i < len(_NUMBERS) else f"{num}."
        date_str = r.created_at.strftime("%d.%m.%Y") if r.created_at else ""
        lines.append(f"{icon} {r.title}")
        if date_str:
            lines[-1] += f" — _{date_str}_"
        item_buttons.append([InlineKeyboardButton(
            text=f"{icon} {_open}",
            callback_data=f"reports:view:{r.id}",
        )])

    # Пагинация / замок для бесплатных
    nav: list[list[InlineKeyboardButton]] = []
    if is_paid:
        row: list[InlineKeyboardButton] = []
        if page > 0:
            row.append(InlineKeyboardButton(text=_prev, callback_data=f"reports:cat:{report_type}:{page - 1}"))
        if (offset + limit) < total:
            row.append(InlineKeyboardButton(text=_next, callback_data=f"reports:cat:{report_type}:{page + 1}"))
        if row:
            nav.append(row)
    elif total > FREE_LIMIT:
        _locked = {
            "ru": f"🔒 Полная история в подписке ({total - FREE_LIMIT} скрыто)",
            "en": f"🔒 Full history with subscription ({total - FREE_LIMIT} hidden)",
            "fa": f"🔒 تاریخچه کامل با اشتراک ({total - FREE_LIMIT} پنهان)",
            "tr": f"🔒 Abonelikle tam geçmiş ({total - FREE_LIMIT} gizli)",
        }.get(lang, f"🔒 Full history with subscription ({total - FREE_LIMIT} hidden)")
        item_buttons.append([InlineKeyboardButton(text=_locked, callback_data="menu:plans")])

    all_buttons = item_buttons + nav + [
        [InlineKeyboardButton(text=_back, callback_data="reports:menu")],
        [InlineKeyboardButton(text=_main_menu, callback_data="menu:main")],
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=all_buttons),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Просмотр разбора ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:view:"))
async def view_report(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    try:
        report_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка")
        return

    report = await get_report_by_id(session, report_id, user.id)
    if not report:
        _nf = {"ru": "Разбор не найден", "en": "Reading not found", "fa": "تفسیر یافت نشد", "tr": "Okuma bulunamadı"}.get(lang, "Reading not found")
        await callback.answer(_nf, show_alert=True)
        return

    lbl = _label(report.report_type, lang)
    date_str = report.created_at.strftime("%d.%m.%Y") if report.created_at else "—"
    _date_l = {"ru": "Дата", "en": "Date", "fa": "تاریخ", "tr": "Tarih"}.get(lang, "Date")
    _back_list = {"ru": "🔙 К списку",              "en": "🔙 To list",          "fa": "🔙 به لیست",      "tr": "🔙 Listeye"}.get(lang, "🔙 To list")
    _share     = {"ru": "📤 Поделиться",             "en": "📤 Share",            "fa": "📤 اشتراک‌گذاری", "tr": "📤 Paylaş"}.get(lang, "📤 Share")
    _ask_q     = {"ru": "🔮 Задать вопрос Бабушке Aisha", "en": "🔮 Ask Grandma Aisha a question",
                  "fa": "🔮 از مادربزرگ آیشا سؤال بپرسید", "tr": "🔮 Büyükanne Aisha'ya soru sor"}.get(lang, "🔮 Ask Grandma Aisha a question")
    _main_menu = {"ru": "🏠 Главное меню",           "en": "🏠 Main menu",        "fa": "🏠 منوی اصلی",    "tr": "🏠 Ana menü"}.get(lang, "🏠 Main menu")

    header = f"{lbl}\n*{report.title}*\n_{_date_l}: {date_str}_\n\n"
    text = _truncate(header + report.content, lang=lang)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_back_list, callback_data=f"reports:cat:{report.report_type}:0"),
            InlineKeyboardButton(text=_share, callback_data=f"reports:share:{report.id}"),
        ],
        [InlineKeyboardButton(text=_ask_q, callback_data="menu:question")],
        [InlineKeyboardButton(text=_main_menu, callback_data="menu:main")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


# ─── Upsell «Спросить глубже» ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:deep:"))
async def report_upsell(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    try:
        report_id = callback.data.split(":")[2]
    except IndexError:
        report_id = "0"

    plan = await get_user_plan(session, user.id)
    is_paid = plan != "free"

    text = {
        "ru": ("✨ *Хотите глубже раскрыть этот разбор?*\n\n"
               "Вы можете задать личный вопрос Тарологу — и получить более детальный ответ "
               "со скрытыми причинами, вероятным развитием событий и советом на ближайшие дни."),
        "en": ("✨ *Want to explore this reading deeper?*\n\n"
               "You can ask a personal question to the Tarot reader — and get a more detailed answer "
               "with hidden causes, likely development and advice for the coming days."),
        "fa": ("✨ *می‌خواهید این تفسیر را عمیق‌تر بررسی کنید؟*\n\n"
               "می‌توانید سؤال شخصی از تاروتیست بپرسید — و پاسخ دقیق‌تری با دلایل پنهان دریافت کنید."),
        "tr": ("✨ *Bu okumayı daha derin incelemek ister misiniz?*\n\n"
               "Tarot okuyucusuna kişisel bir soru sorabilirsiniz — gizli nedenler ve önerilerle daha ayrıntılı cevap alın."),
    }.get(lang, "✨ *Want to explore this reading deeper?*")

    _ask_q  = {"ru": "🔮 Задать вопрос Бабушке Aisha",  "en": "🔮 Ask Grandma Aisha",
               "fa": "🔮 از مادربزرگ آیشا بپرسید",     "tr": "🔮 Büyükanne Aisha'ya sor"}.get(lang, "🔮 Ask Grandma Aisha")
    _ask_ql = {"ru": "🔒 Задать вопрос Бабушке Aisha",  "en": "🔒 Ask Grandma Aisha",
               "fa": "🔒 از مادربزرگ آیشا بپرسید",     "tr": "🔒 Büyükanne Aisha'ya sor"}.get(lang, "🔒 Ask Grandma Aisha")
    _plans  = {"ru": "📜 Тарифы",   "en": "📜 Plans",   "fa": "📜 طرح‌ها", "tr": "📜 Planlar"}.get(lang, "📜 Plans")
    _back   = {"ru": "◀️ Назад",    "en": "◀️ Back",    "fa": "◀️ بازگشت", "tr": "◀️ Geri"}.get(lang, "◀️ Back")

    question_btn_text = _ask_q if is_paid else _ask_ql
    rows = [
        [InlineKeyboardButton(text=question_btn_text, callback_data="menu:question")],
        [InlineKeyboardButton(text=_back, callback_data=f"reports:view:{report_id}")],
    ]
    if not is_paid:
        rows.insert(1, [InlineKeyboardButton(text=_plans, callback_data="menu:plans")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Поделиться ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:share:"))
async def share_report(callback: CallbackQuery, user: User, session: AsyncSession, lang: str = "ru"):
    try:
        report_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer()
        return

    await callback.answer()  # сразу, до async-работы

    try:
        import html as _html
        from bot.handlers.share import _get_bot_username
        report = await get_report_by_id(session, report_id, user.id)
        if not report:
            return

        bot_username = await _get_bot_username(callback.bot)
        bot_link = f"https://t.me/{bot_username}"

        label = REPORT_TYPE_LABELS.get(report.report_type, "Разбор")
        date_str = report.created_at.strftime("%d.%m.%Y") if report.created_at else ""

        # HTML-режим — единственный надёжный способ сделать гиперссылку
        # когда URL содержит подчёркивания (Markdown v1 ломает их как курсив)
        share_text = (
            f"{label} — <b>{_html.escape(report.title)}</b>\n"
            f"<i>{_html.escape(date_str)}</i>\n\n"
            f"{_html.escape(_truncate(report.content, 2000))}\n\n"
            f'— <a href="{bot_link}">Aisha AI 🔮</a>'
        )

        _fwd = {"ru": "👇 Перешли результат другу", "en": "👇 Forward the result to a friend",
                "fa": "👇 نتیجه را به دوستتان ارسال کنید", "tr": "👇 Sonucu arkadaşına ilet"}.get(lang, "👇 Forward the result to a friend")
        await callback.message.answer(_fwd)
        await callback.message.answer(share_text, parse_mode="HTML")
    except Exception:
        logger.exception("share_report failed for user %s", user.telegram_id)
