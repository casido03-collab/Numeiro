"""Совместимость двух людей — FSM + AI."""
import json
from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from bot.models.user import User
from bot.services.compatibility import calculate_compatibility
from bot.services.cache import get_cached, set_cached, make_cache_key
from bot.services.limits import check_limit, consume_limit
from bot.services.ai_service import generate
from bot.prompts.prompts import COMPATIBILITY_PROMPT
from bot.i18n.translations import t
from bot.keyboards.main import relation_type_menu, limit_reached_keyboard, back_to_main
from bot.keyboards.reply import ALL_REPLY_TEXTS as _ALL_REPLY
from bot.services.thinking import random_thinking
from bot.utils import parse_birth_date as _parse_compat_date, safe_edit_ai

router = Router()

from bot.keyboards.main import main_menu  # noqa: E402


@router.callback_query(F.data == "compat:cancel")
async def compat_cancel(callback: CallbackQuery, state: FSMContext, user: User):
    await state.clear()
    name = user.first_name or "друг"
    await callback.message.edit_text(
        f"✨ *{name}*, выберите что вас интересует:",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


RELATION_NAMES = {
    "love": "романтические отношения",
    "marriage": "брак",
    "friendship": "дружба",
    "work": "рабочие отношения",
    "ex": "отношения с бывшим партнёром",
    "potential": "потенциальный партнёр",
}


def _relation(relation: str, lang: str = "ru") -> str:
    """Тип отношений на языке пользователя."""
    translated = t(f"relation_{relation}", lang)
    if translated == f"relation_{relation}":
        return RELATION_NAMES.get(relation, relation)
    return translated


class CompatibilityFSM(StatesGroup):
    waiting_partner_date = State()
    waiting_relation_type = State()


def _parse_date(text: str) -> date | None:
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


@router.callback_query(F.data == "menu:compatibility")
@router.callback_query(F.data == "compat:start")
async def compat_start(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext, lang: str = "ru"):
    from bot.services.limits import has_credit, is_vip, check_vip_limit
    from bot.keyboards.main import payment_method_keyboard as _pay_kb

    _is_vip = await is_vip(user.id)
    if not _is_vip and not await has_credit(user.id, "compatibility"):
        _locked = {
            "ru": (
                "💞 *Совместимость*\n\n"
                "Введите дату рождения второго человека — и я разберу вашу совместимость по нумерологии.\n\n"
                "Где вы усиливаете друг друга, где возникают трения и как выстроить гармонию.\n\n"
                "Работает для романтики, дружбы и бизнеса.\n\n"
                "💳 Стоимость: *99 ₽* или *99 ⭐*"
            ),
            "en": (
                "💞 *Compatibility*\n\n"
                "Enter the second person's date of birth — and I'll break down your compatibility by numerology.\n\n"
                "Where you strengthen each other, where friction arises and how to build harmony.\n\n"
                "Works for romance, friendship and business.\n\n"
                "💳 Price: *99 ⭐*"
            ),
            "fa": (
                "💞 *سازگاری*\n\n"
                "تاریخ تولد نفر دوم را وارد کنید — و من سازگاری شما را از نظر عددشناسی بررسی می‌کنم.\n\n"
                "💳 قیمت: *99 ⭐*"
            ),
            "tr": (
                "💞 *Uyumluluk*\n\n"
                "İkinci kişinin doğum tarihini girin — numerolojiye göre uyumluluğunuzu analiz edeceğim.\n\n"
                "Birbirinizi nerede güçlendirdiğinizi, nerede sürtüşme yaşandığını ve nasıl uyum kurulacağını göreceksiniz.\n\n"
                "💳 Fiyat: *99 ⭐*"
            ),
        }.get(lang, "💞 *Compatibility*\n\nNumerology-based compatibility reading for two people.\n\n💳 Price: *99 ⭐*")
        await callback.message.edit_text(_locked, reply_markup=_pay_kb("compatibility", 99, 99, lang), parse_mode="Markdown")
        await callback.answer()
        return

    if _is_vip and not await check_vip_limit(user.id, "compatibility"):
        _exhausted = {
            "ru": "💎 Лимит VIP по этому разделу исчерпан на этот месяц.",
            "en": "💎 VIP limit for this section exhausted this month.",
            "fa": "💎 محدودیت VIP برای این بخش تمام شده.",
            "tr": "💎 Bu bölüm için VIP limitiniz doldu.",
        }.get(lang, "💎 VIP limit exhausted.")
        await callback.message.edit_text(_exhausted, reply_markup=back_to_main(), parse_mode="Markdown")
        await callback.answer()
        return

    if not user.birth_date:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            "✨ Сначала укажи свою дату рождения — после этого вернёмся сюда.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Ввести дату рождения", callback_data="birth_date:collect:menu:compatibility")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:main")],
            ]),
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    await state.update_data(lang=lang)
    _compat_prompt = {
        "ru": "💞 *Совместимость*\n\nВведи дату рождения второго человека в формате *ДД.ММ.ГГГГ*",
        "en": "💞 *Compatibility*\n\nEnter the second person's birth date in format *DD.MM.YYYY*",
        "fa": "💞 *سازگاری*\n\nتاریخ تولد نفر دوم را به صورت *DD.MM.YYYY* وارد کنید",
        "tr": "💞 *Uyumluluk*\n\nİkinci kişinin doğum tarihini *GG.AA.YYYY* formatında girin",
    }.get(lang, "💞 *Compatibility*\n\nEnter the second person's birth date in format *DD.MM.YYYY*")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(
        _compat_prompt,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_back", lang), callback_data="compat:cancel")]
        ]),
        parse_mode="Markdown",
    )
    await state.set_state(CompatibilityFSM.waiting_partner_date)
    await callback.answer()


@router.message(CompatibilityFSM.waiting_partner_date, ~F.text.in_(_ALL_REPLY))
async def receive_partner_date(message: Message, state: FSMContext):
    partner_date = _parse_date(message.text or "")
    if not partner_date:
        await message.answer(
            "❌ Не могу распознать дату. Введи в формате *ДД.ММ.ГГГГ*",
            parse_mode="Markdown",
        )
        return

    if partner_date.year < 1900 or partner_date > date.today():
        await message.answer("❌ Пожалуйста, введи корректную дату рождения.")
        return

    await state.update_data(partner_date=partner_date.strftime("%d.%m.%Y"))
    await message.answer(
        "💞 Теперь выбери тип связи:",
        reply_markup=relation_type_menu(),
    )
    await state.set_state(CompatibilityFSM.waiting_relation_type)


@router.callback_query(F.data.startswith("compat:type:"), CompatibilityFSM.waiting_relation_type)
async def receive_relation_type(callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, lang: str = "ru"):
    relation_type = callback.data.split(":")[-1]
    data = await state.get_data()
    partner_date_str = data.get("partner_date")
    lang = data.get("lang", lang)
    await state.clear()

    if not partner_date_str:
        await callback.message.edit_text("❌ Ошибка. Начни сначала.", reply_markup=back_to_main())
        await callback.answer()
        return

    thinking_msg = await callback.message.edit_text(random_thinking())

    user_date = _parse_compat_date(user.birth_date)
    partner_date = _parse_compat_date(partner_date_str)

    if not user_date or not partner_date:
        await thinking_msg.edit_text("❌ Ошибка при разборе дат.")
        await callback.answer()
        return

    cache_key = make_cache_key("compat", user.birth_date, partner_date_str, relation_type)
    cached = await get_cached(cache_key)

    if not cached:
        compat = calculate_compatibility(user_date, partner_date, relation_type)
        context = {
            "name": user.first_name or "друг",
            "user_birth": user.birth_date,
            "partner_birth": partner_date_str,
            "relation_type": _relation(relation_type, lang),
            "compatibility": compat,
        }
        user_msg = f"Анализируй совместимость.\nДанные: {json.dumps(context, ensure_ascii=False)}"
        cached = await generate(
            session, user.id, "compatibility",
            COMPATIBILITY_PROMPT(lang), user_msg,
            complexity="medium", max_tokens=700,
        )
        await set_cached(cache_key, cached, ttl=3600 * 24 * 30)

        # Сохраняем отчёт
        from bot.models.user import CompatibilityReport
        report = CompatibilityReport(
            user_id=user.id,
            user_birth_date=user.birth_date,
            partner_birth_date=partner_date_str,
            relation_type=relation_type,
            content=cached,
            cache_key=cache_key,
        )
        session.add(report)
        await session.commit()

    from bot.services.reports_service import save_report
    await save_report(
        session, user.id, "compatibility",
        title=f"Совместимость | {RELATION_NAMES.get(relation_type, relation_type)}",  # история всегда ru
        content=cached,
        metadata={"partner_birth": partner_date_str, "relation_type": relation_type},
    )
    if await is_vip(user.id):
        from bot.services.limits import use_vip_limit
        await use_vip_limit(user.id, "compatibility")
    else:
        from bot.services.limits import use_credit
        await use_credit(user.id, "compatibility")

    _friend = {"ru": "друг", "en": "friend", "fa": "دوست", "tr": "dostum"}.get(lang, "friend")
    name = user.first_name or _friend
    relation_name = _relation(relation_type, lang)
    _type_label = {"ru": "Тип связи", "en": "Relationship type", "fa": "نوع رابطه", "tr": "İlişki türü"}.get(lang, "Relationship type")
    _compat_title = {"ru": "Совместимость", "en": "Compatibility", "fa": "سازگاری", "tr": "Uyumluluk"}.get(lang, "Compatibility")
    header = f"💞 *{_compat_title} — {name}*\n_{_type_label}: {relation_name}_\n\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться результатом", callback_data=f"share:compat:{cache_key[:20]}")],
        [InlineKeyboardButton(text="💞 Другая совместимость", callback_data="compat:start")],
        [InlineKeyboardButton(text="❤️ Что такое кармические отношения?", callback_data="content:compatibility")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="menu:main")],
    ])
    await safe_edit_ai(thinking_msg, header + cached, reply_markup=kb)
    await callback.answer()
