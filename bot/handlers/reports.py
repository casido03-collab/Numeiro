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

REPORT_TYPE_LABELS: dict[str, str] = {
    "tarot_card":        "🃏 Карты дня",
    "weekly_forecast":   "📅 Прогнозы",
    "compatibility":     "💞 Совместимости",
    "personal_question": "🔮 Личные вопросы",
    "destiny_matrix":    "🌟 Матрица судьбы",
    "daily_energy":      "⚡ Энергия дня",
    "date_selection":    "📆 Подбор дат",
    "mini_report":       "✨ Мини-разборы",
}

CATEGORY_ORDER = [
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


def _truncate(text: str, limit: int = 3600) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "\n\n_… текст обрезан_"


# ─── Главный экран раздела ────────────────────────────────────────────────────

@router.callback_query(F.data == "reports:menu")
async def my_reports_menu(callback: CallbackQuery, user: User, session: AsyncSession):
    counts = await get_categories_with_counts(session, user.id)

    if not counts:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Получить прогноз", callback_data="menu:weekly")],
            [InlineKeyboardButton(text="💞 Проверить совместимость", callback_data="compat:start")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
        ])
        await callback.message.edit_text(
            "🌀 *У вас пока нет сохранённых разборов.*\n\n"
            "Начните с первого прогноза или совместимости — и они появятся здесь.",
            reply_markup=kb,
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    lines: list[str] = []
    buttons: list[list[InlineKeyboardButton]] = []

    for rtype in CATEGORY_ORDER:
        cnt = counts.get(rtype, 0)
        if cnt == 0:
            continue
        label = REPORT_TYPE_LABELS[rtype]
        lines.append(f"{label} — {cnt}")
        buttons.append([InlineKeyboardButton(
            text=f"{label} ({cnt})",
            callback_data=f"reports:cat:{rtype}:0",
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")])

    text = (
        "🌀 *Ваши разборы*\n\n"
        "Здесь сохраняются ваши прогнозы, совместимости и личные ответы.\n"
        "Вы можете вернуться к ним в любой момент.\n\n"
        + "\n".join(lines)
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Список по категории ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:cat:"))
async def reports_category(callback: CallbackQuery, user: User, session: AsyncSession):
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
    label = REPORT_TYPE_LABELS.get(report_type, report_type)

    if not reports:
        await callback.message.edit_text(
            f"{label}\n\n_Разборов этого типа пока нет._",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="reports:menu")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # Список строк
    lines = [f"*{label}*\n"]
    item_buttons: list[list[InlineKeyboardButton]] = []
    for i, r in enumerate(reports):
        num = offset + i + 1
        icon = _NUMBERS[i] if i < len(_NUMBERS) else f"{num}."
        date_str = r.created_at.strftime("%d.%m.%Y") if r.created_at else ""
        lines.append(f"{icon} {r.title}")
        if date_str:
            lines[-1] += f" — _{date_str}_"
        item_buttons.append([InlineKeyboardButton(
            text=f"{icon} Открыть",
            callback_data=f"reports:view:{r.id}",
        )])

    # Пагинация / замок для бесплатных
    nav: list[list[InlineKeyboardButton]] = []
    if is_paid:
        row: list[InlineKeyboardButton] = []
        if page > 0:
            row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"reports:cat:{report_type}:{page - 1}"))
        if (offset + limit) < total:
            row.append(InlineKeyboardButton(text="➡️ Ещё", callback_data=f"reports:cat:{report_type}:{page + 1}"))
        if row:
            nav.append(row)
    elif total > FREE_LIMIT:
        item_buttons.append([InlineKeyboardButton(
            text=f"🔒 Полная история в подписке ({total - FREE_LIMIT} скрыто)",
            callback_data="menu:plans",
        )])

    all_buttons = item_buttons + nav + [
        [InlineKeyboardButton(text="◀️ Назад", callback_data="reports:menu")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="menu:main")],
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=all_buttons),
        parse_mode="Markdown",
    )
    await callback.answer()


# ─── Просмотр разбора ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:view:"))
async def view_report(callback: CallbackQuery, user: User, session: AsyncSession):
    try:
        report_id = int(callback.data.split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка")
        return

    report = await get_report_by_id(session, report_id, user.id)
    if not report:
        await callback.answer("Разбор не найден", show_alert=True)
        return

    label = REPORT_TYPE_LABELS.get(report.report_type, "Разбор")
    date_str = report.created_at.strftime("%d.%m.%Y") if report.created_at else "—"

    header = f"{label}\n*{report.title}*\n_Дата: {date_str}_\n\n"
    text = _truncate(header + report.content)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 К списку", callback_data=f"reports:cat:{report.report_type}:0"),
            InlineKeyboardButton(text="📤 Поделиться", callback_data=f"reports:share:{report.id}"),
        ],
        [InlineKeyboardButton(text="🔮 Спросить глубже", url="https://t.me/m/-Ekcn86bNmU0")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")],
    ])
    await safe_edit(callback.message, text, reply_markup=kb)
    await callback.answer()


# ─── Upsell «Спросить глубже» ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:deep:"))
async def report_upsell(callback: CallbackQuery, user: User, session: AsyncSession):
    try:
        report_id = callback.data.split(":")[2]
    except IndexError:
        report_id = "0"

    plan = await get_user_plan(session, user.id)
    is_paid = plan != "free"

    text = (
        "✨ *Хотите глубже раскрыть этот разбор?*\n\n"
        "Вы можете задать личный вопрос Тарологу — и получить более детальный ответ "
        "со скрытыми причинами, вероятным развитием событий и советом на ближайшие дни."
    )

    # Для платных пользователей убираем замок — они уже оплатили
    question_btn_text = "💬 Задать вопрос Тарологу" if is_paid else "🔒 Задать вопрос Тарологу"

    rows = [
        [InlineKeyboardButton(text=question_btn_text, callback_data="menu:question")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"reports:view:{report_id}")],
    ]
    # Кнопку «Тарифы» показываем только тем, у кого нет подписки
    if not is_paid:
        rows.insert(1, [InlineKeyboardButton(text="📜 Тарифы", callback_data="menu:plans")])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


# ─── Поделиться ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reports:share:"))
async def share_report(callback: CallbackQuery, user: User, session: AsyncSession):
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

        await callback.message.answer("👇 Перешли результат другу")
        await callback.message.answer(share_text, parse_mode="HTML")
    except Exception:
        logger.exception("share_report failed for user %s", user.telegram_id)
