"""Команды администратора."""
import logging
from datetime import datetime, timezone, timedelta, date
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, Date
from bot.models.user import User, Subscription, Payment, AIRequest, PlanEnum, SubscriptionStatusEnum, Referral
from config import settings

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list


# ─── /ping ────────────────────────────────────────────────────────────────────

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(f"✅ Бот работает\nAdmin ID: `{message.from_user.id}`", parse_mode="Markdown")


# ─── /stats ───────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    try:
        from bot.models.user import UserProfile

        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0

        # Пользователи, реально прошедшие онбординг (onboarding_done = true в preferences)
        onboarded = (await session.execute(
            select(func.count(UserProfile.id)).where(
                UserProfile.preferences.op("->>")(  # type: ignore[operator]
                    "onboarding_done"
                ) == "true"
            )
        )).scalar() or 0

        active_subs = (await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatusEnum.active,
                Subscription.plan != PlanEnum.free,
            )
        )).scalar() or 0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        new_today = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )).scalar() or 0
        new_yesterday = (await session.execute(
            select(func.count(User.id)).where(
                User.created_at >= yesterday_start, User.created_at < today_start
            )
        )).scalar() or 0
        new_week = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )).scalar() or 0

        # Рублёвый доход (хранится в копейках → делим на 100)
        today_revenue_rub = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= today_start,
                Payment.currency == "RUB",
            )
        )).scalar() or 0

        month_revenue_rub = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= month_start,
                Payment.currency == "RUB",
            )
        )).scalar() or 0

        # Stars-доход
        today_revenue_stars = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= today_start,
                Payment.currency == "XTR",
            )
        )).scalar() or 0

        month_revenue_stars = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= month_start,
                Payment.currency == "XTR",
            )
        )).scalar() or 0

        ai_cost_today = (await session.execute(
            select(func.sum(AIRequest.estimated_cost)).where(
                AIRequest.created_at >= today_start
            )
        )).scalar() or 0

        ai_cost_month = (await session.execute(
            select(func.sum(AIRequest.estimated_cost)).where(
                AIRequest.created_at >= month_start
            )
        )).scalar() or 0

        # Покупки по услугам (все время)
        product_rows = (await session.execute(
            select(Payment.product_type, func.count(Payment.id))
            .where(Payment.status == "completed")
            .group_by(Payment.product_type)
            .order_by(func.count(Payment.id).desc())
        )).all()

        _product_labels = {
            "product:tarot_card":        "🃏 Карта дня",
            "product:personal_question": "🔮 Личный вопрос",
            "product:mini_reading":      "📖 Мини-разбор",
            "product:full_matrix":       "🌟 Матрица судьбы",
            "product:compatibility":     "💞 Совместимость",
            "product:weekly_report":     "📅 Расклад на неделю",
            "product:date_selection":    "🎯 Подбор дат",
        }
        products_text = ""
        for pt, cnt in product_rows:
            label = _product_labels.get(pt, pt)
            products_text += f"• {label}: {cnt}\n"
        if not products_text:
            products_text = "• Покупок пока нет\n"

        today_rub = today_revenue_rub // 100
        month_rub = month_revenue_rub // 100

        revenue_text = f"• Сегодня: {today_rub} ₽"
        if today_revenue_stars:
            revenue_text += f" + {today_revenue_stars} ⭐"
        revenue_text += f"\n• Месяц: {month_rub} ₽"
        if month_revenue_stars:
            revenue_text += f" + {month_revenue_stars} ⭐"

        text = (
            f"📊 *Статистика Aisha AI*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 В базе: *{total_users}* (все кто написал)\n"
            f"✅ Прошли знакомство: *{onboarded}*\n\n"
            f"📈 *Новые пользователи:*\n"
            f"• Сегодня: *{new_today}*\n"
            f"• Вчера: *{new_yesterday}*\n"
            f"• Эта неделя: *{new_week}*\n\n"
            f"🛍 *Продажи по услугам:*\n"
            f"{products_text}\n"
            f"💰 *Доход:*\n"
            f"{revenue_text}\n\n"
            f"🤖 *AI расходы:*\n"
            f"• Сегодня: ${ai_cost_today:.4f}\n"
            f"• Месяц: ${ai_cost_month:.4f}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_stats error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /user ────────────────────────────────────────────────────────────────────

@router.message(Command("user"))
async def cmd_user(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: `/user <telegram_id>`", parse_mode="Markdown")
        return

    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный telegram\\_id", parse_mode="Markdown")
        return

    try:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        sub_result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
        sub = sub_result.scalar_one_or_none()

        ai_cost = (await session.execute(
            select(func.sum(AIRequest.estimated_cost)).where(AIRequest.user_id == user.id)
        )).scalar() or 0

        ai_requests = (await session.execute(
            select(func.count(AIRequest.id)).where(AIRequest.user_id == user.id)
        )).scalar() or 0

        # Платежи пользователя
        payment_rows = (await session.execute(
            select(Payment.product_type, Payment.amount, Payment.currency, Payment.created_at)
            .where(Payment.user_id == user.id, Payment.status == "completed")
            .order_by(Payment.created_at.desc())
            .limit(10)
        )).all()

        payments_rub = sum(p.amount for p in payment_rows if p.currency == "RUB") // 100
        payments_stars = sum(p.amount for p in payment_rows if p.currency == "XTR")

        # Redis-кредиты (реальный доступ к услугам)
        from bot.services.cache import get_redis
        r = await get_redis()
        _product_keys = [
            "tarot_card", "personal_question", "mini_reading",
            "full_matrix", "compatibility", "weekly_report", "date_selection",
        ]
        credits_text = ""
        for pk in _product_keys:
            val = await r.get(f"oneoff:{pk}:{user.id}")
            if val and int(val) > 0:
                credits_text += f"  ✅ {pk}: {val}\n"
        if not credits_text:
            credits_text = "  нет активных кредитов\n"

        _product_labels = {
            "product:tarot_card":        "🃏 Карта дня",
            "product:personal_question": "🔮 Личный вопрос",
            "product:mini_reading":      "📖 Мини-разбор",
            "product:full_matrix":       "🌟 Матрица судьбы",
            "product:compatibility":     "💞 Совместимость",
            "product:weekly_report":     "📅 Расклад на неделю",
            "product:date_selection":    "🎯 Подбор дат",
        }
        payments_text = ""
        for p in payment_rows:
            label = _product_labels.get(p.product_type, p.product_type)
            amt = f"{p.amount // 100} ₽" if p.currency == "RUB" else f"{p.amount} ⭐"
            dt = p.created_at.strftime("%d.%m %H:%M") if p.created_at else "—"
            payments_text += f"  {dt} — {label} — {amt}\n"
        if not payments_text:
            payments_text = "  нет платежей\n"

        plan = sub.plan.value if sub else "free"
        created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"

        paid_total = f"{payments_rub} ₽"
        if payments_stars:
            paid_total += f" + {payments_stars} ⭐"

        text = (
            f"👤 <b>Пользователь #{user.id}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Telegram ID: <code>{user.telegram_id}</code>\n"
            f"Имя: {user.first_name or '—'}\n"
            f"Username: @{user.username or '—'}\n"
            f"Дата рождения: {user.birth_date or '—'}\n"
            f"Зарегистрирован: {created}\n\n"
            f"🛍 <b>Покупки:</b>\n{payments_text}\n"
            f"💰 Итого оплачено: {paid_total}\n\n"
            f"🔑 <b>Активные кредиты (Redis):</b>\n{credits_text}\n"
            f"🤖 AI запросов: {ai_requests} | Расходы: ${ai_cost:.4f}"
        )
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.exception("cmd_user error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /recent ─────────────────────────────────────────────────────────────────

@router.message(Command("recent"))
async def cmd_recent(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    try:
        rows = (await session.execute(
            select(Payment.created_at, Payment.product_type, Payment.amount, Payment.currency, User.telegram_id, User.first_name)
            .join(User, User.id == Payment.user_id)
            .where(Payment.status == "completed")
            .order_by(Payment.created_at.desc())
            .limit(20)
        )).all()

        _product_labels = {
            "product:tarot_card":        "🃏 Карта дня",
            "product:personal_question": "🔮 Личный вопрос",
            "product:mini_reading":      "📖 Мини-разбор",
            "product:full_matrix":       "🌟 Матрица судьбы",
            "product:compatibility":     "💞 Совместимость",
            "product:weekly_report":     "📅 Расклад на неделю",
            "product:date_selection":    "🎯 Подбор дат",
        }

        if not rows:
            await message.answer("Покупок ещё нет")
            return

        lines = ["📋 *Последние 20 покупок:*\n"]
        for r in rows:
            label = _product_labels.get(r.product_type, r.product_type)
            amt = f"{r.amount // 100} ₽" if r.currency == "RUB" else f"{r.amount} ⭐"
            dt = r.created_at.strftime("%d.%m %H:%M") if r.created_at else "—"
            name = r.first_name or "—"
            lines.append(f"`{dt}` — {label} — {amt}\n  👤 {name} (`{r.telegram_id}`)")

        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_recent error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /grant ───────────────────────────────────────────────────────────────────

@router.message(Command("grant"))
async def cmd_grant(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 4:
        await message.answer(
            "Использование: `/grant <telegram_id> <plan> <days>`\n"
            "days=0 → бессрочная\n"
            "Пример: `/grant 123456789 premium 30`",
            parse_mode="Markdown",
        )
        return

    try:
        tg_id = int(args[1])
        plan_key = args[2].lower()
        days = int(args[3])
    except (ValueError, IndexError):
        await message.answer("❌ Неверные аргументы")
        return

    if plan_key not in ("lite", "premium", "pro", "free"):
        await message.answer("❌ Допустимые планы: free, lite, premium, pro")
        return

    try:
        result = await session.execute(select(User).where(User.telegram_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        expires = None if days == 0 else datetime.now(timezone.utc) + timedelta(days=days)

        sub_result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
        sub = sub_result.scalar_one_or_none()

        if sub:
            sub.plan = PlanEnum(plan_key)
            sub.status = SubscriptionStatusEnum.active
            sub.expires_at = expires
        else:
            sub = Subscription(
                user_id=user.id,
                plan=PlanEnum(plan_key),
                status=SubscriptionStatusEnum.active,
                expires_at=expires,
            )
            session.add(sub)

        await session.commit()

        duration_str = "бессрочно ∞" if days == 0 else f"на {days} дней"
        await message.answer(
            f"✅ Пользователю `{tg_id}` выдан тариф *{plan_key}* {duration_str}",
            parse_mode="Markdown",
        )

        try:
            await message.bot.send_message(
                tg_id,
                f"🎁 *Тариф {plan_key.title()} активирован!*\n"
                + ("Доступ открыт бессрочно." if days == 0 else f"Доступ открыт на {days} дней."),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    except Exception as e:
        logger.exception("cmd_grant error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /costs ───────────────────────────────────────────────────────────────────

@router.message(Command("costs"))
async def cmd_costs(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        today_cost = (await session.execute(
            select(func.sum(AIRequest.estimated_cost)).where(AIRequest.created_at >= today_start)
        )).scalar() or 0

        month_cost = (await session.execute(
            select(func.sum(AIRequest.estimated_cost)).where(AIRequest.created_at >= month_start)
        )).scalar() or 0

        total_cost = (await session.execute(
            select(func.sum(AIRequest.estimated_cost))
        )).scalar() or 0

        total_requests = (await session.execute(
            select(func.count(AIRequest.id))
        )).scalar() or 0

        by_model = await session.execute(
            select(AIRequest.model, func.count(AIRequest.id), func.sum(AIRequest.estimated_cost))
            .group_by(AIRequest.model)
            .order_by(func.count(AIRequest.id).desc())
        )
        model_rows = by_model.all()
        model_stats = "\n".join(
            f"• {m or 'unknown'}: {c} запросов, ${(cost or 0):.4f}"
            for m, c, cost in model_rows
        ) or "нет данных"

        by_type = await session.execute(
            select(AIRequest.request_type, func.count(AIRequest.id))
            .group_by(AIRequest.request_type)
            .order_by(func.count(AIRequest.id).desc())
            .limit(10)
        )
        type_stats = "\n".join(
            f"• {t or 'unknown'}: {c}"
            for t, c in by_type.all()
        ) or "нет данных"

        text = (
            f"💸 *AI Расходы*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Сегодня: ${today_cost:.4f}\n"
            f"Месяц: ${month_cost:.4f}\n"
            f"Всего: ${total_cost:.4f}\n"
            f"Всего запросов: {total_requests}\n\n"
            f"*По моделям:*\n{model_stats}\n\n"
            f"*Топ типов:*\n{type_stats}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_costs error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /limits ──────────────────────────────────────────────────────────────────

@router.message(Command("limits"))
async def cmd_limits(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    try:
        from bot.models.user import UsageLimits
        from sqlalchemy import func
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Берём максимум AI-сообщений по каждому пользователю (все периоды)
        # Это покрывает и free_total, и дневные, и подписочные записи
        top_users = await session.execute(
            select(
                UsageLimits.user_id,
                func.sum(UsageLimits.ai_messages).label("total_ai"),
                User.first_name,
                User.telegram_id,
            )
            .join(User, User.id == UsageLimits.user_id)
            .group_by(UsageLimits.user_id, User.first_name, User.telegram_id)
            .order_by(func.sum(UsageLimits.ai_messages).desc())
            .limit(10)
        )
        rows = top_users.all()

        if not rows:
            await message.answer("📊 *AI-использование:*\n\nНет данных", parse_mode="Markdown")
            return

        lines = []
        for i, (uid, msgs, name, tg_id) in enumerate(rows, 1):
            raw   = name or f"id{tg_id}"
            label = raw.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
            lines.append(f"{i}. {label} (`{tg_id}`): *{msgs}* AI-сообщений")

        # Ежедневная статистика из Redis
        from bot.services.cache import get_redis
        r = await get_redis()
        ai_count_today = int(await r.get(f"stats:ai:count:{today}") or 0)
        ai_users_today = await r.scard(f"stats:ai:users:{today}")

        header = (
            f"📊 *AI-статистика*\n\n"
            f"📅 *Сегодня ({today}):*\n"
            f"• Активных пользователей: *{ai_users_today}*\n"
            f"• AI-запросов: *{ai_count_today}*\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏆 *Топ по AI (всего):*\n\n"
        )

        await message.answer(
            header + "\n".join(lines),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("cmd_limits error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /broadcast ───────────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: `/broadcast <текст>`", parse_mode="Markdown")
        return

    try:
        users = (await session.execute(
            select(User.telegram_id).where(User.is_blocked == False)
        )).scalars().all()

        await message.answer(f"📤 Начинаю рассылку для {len(users)} пользователей...")

        sent = 0
        failed = 0
        for tg_id in users:
            try:
                await message.bot.send_message(tg_id, text, parse_mode="Markdown")
                sent += 1
            except Exception:
                failed += 1

        await message.answer(f"✅ Рассылка завершена: отправлено *{sent}*, ошибок *{failed}*", parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_broadcast error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /referrals ───────────────────────────────────────────────────────────────

@router.message(Command("referrals"))
async def cmd_referrals(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Общие цифры
        total_refs = (await session.execute(select(func.count(Referral.id)))).scalar() or 0
        refs_today = (await session.execute(
            select(func.count(Referral.id)).where(Referral.created_at >= today_start)
        )).scalar() or 0
        refs_week = (await session.execute(
            select(func.count(Referral.id)).where(Referral.created_at >= week_start)
        )).scalar() or 0
        refs_month = (await session.execute(
            select(func.count(Referral.id)).where(Referral.created_at >= month_start)
        )).scalar() or 0

        # Сколько уникальных пользователей поделились ссылкой (привели хоть одного)
        unique_inviters = (await session.execute(
            select(func.count(func.distinct(Referral.inviter_telegram_id)))
        )).scalar() or 0

        # Сколько приглашённых совершили покупку
        with_purchase = (await session.execute(
            select(func.count(Referral.id)).where(Referral.purchase_status == True)
        )).scalar() or 0

        # Конверсия
        conversion = (with_purchase / total_refs * 100) if total_refs > 0 else 0

        # Топ-10 инвайтеров (по количеству приглашённых)
        from sqlalchemy import Integer as SAInteger, case
        top_inviters_q = await session.execute(
            select(
                Referral.inviter_telegram_id,
                func.count(Referral.id).label("invited_count"),
                func.sum(
                    case((Referral.purchase_status == True, 1), else_=0)
                ).label("purchases"),
            )
            .group_by(Referral.inviter_telegram_id)
            .order_by(func.count(Referral.id).desc())
            .limit(10)
        )
        top_rows = top_inviters_q.all()

        # Собираем имена инвайтеров из таблицы users
        inviter_ids = [row[0] for row in top_rows]
        names_q = await session.execute(
            select(User.telegram_id, User.first_name, User.username)
            .where(User.telegram_id.in_(inviter_ids))
        )
        names_map = {row.telegram_id: (row.first_name or row.username or str(row.telegram_id)) for row in names_q}

        top_lines = []
        for i, (tg_id, count, purchases) in enumerate(top_rows, 1):
            name = names_map.get(tg_id, str(tg_id))
            purchases = purchases or 0
            top_lines.append(f"{i}. {name} (`{tg_id}`): *{count}* чел. → {purchases} покупок")

        top_block = "\n".join(top_lines) if top_lines else "нет данных"

        text = (
            f"🔗 *Реферальная статистика*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 Всего приглашено: *{total_refs}*\n"
            f"• Сегодня: *{refs_today}*\n"
            f"• Эта неделя: *{refs_week}*\n"
            f"• Этот месяц: *{refs_month}*\n\n"
            f"👤 Уникальных инвайтеров: *{unique_inviters}*\n"
            f"💰 Совершили покупку: *{with_purchase}*\n"
            f"📈 Конверсия в покупку: *{conversion:.1f}%*\n\n"
            f"🏆 *Топ инвайтеры:*\n{top_block}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_referrals error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /unlimit ─────────────────────────────────────────────────────────────────

@router.message(Command("unlimit"))
async def cmd_unlimit(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer(
            "Использование: `/unlimit <telegram_id> <количество>`\n"
            "Пример: `/unlimit 1715461306 50`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(parts[1])
        extra = int(parts[2])

        from bot.services.cache import get_redis
        from bot.business_dialog.session_manager import get_biz_conn, get_profile

        r = await get_redis()
        today = date.today().isoformat()

        day_key = f"biz_day:{target_id}:{today}"
        day_count = int(await r.get(day_key) or 0)

        new_limit = day_count + extra
        limit_key = f"biz_day_limit:{target_id}:{today}"
        await r.set(limit_key, str(new_limit), ex=86400)
        await r.delete(f"biz_day_notif:{target_id}:{today}")

        profile = await get_profile(target_id)
        name = profile.get("name") or str(target_id)

        await message.answer(
            f"✅ Лимит расширен для *{name}* (`{target_id}`)\n"
            f"Использовано сегодня: {day_count}\n"
            f"Новый лимит: {new_limit} \\(\\+{extra}\\)",
            parse_mode="Markdown",
        )

        _RESUME_MSG = "🙏 Простите, отвлеклась — продолжаем с вами диалог."
        biz_conn_id = await get_biz_conn(target_id)
        try:
            send_kw = {"chat_id": target_id, "text": _RESUME_MSG, "parse_mode": None}
            if biz_conn_id:
                send_kw["business_connection_id"] = biz_conn_id
            await message.bot.send_message(**send_kw)
        except Exception as e:
            await message.answer(f"⚠️ Не удалось отправить клиенту: `{e}`", parse_mode="Markdown")

    except Exception as e:
        logger.exception("cmd_unlimit error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /ages ────────────────────────────────────────────────────────────────────

@router.message(Command("ages"))
async def cmd_ages(message: Message, session: AsyncSession):
    """Возраст пользователей, зарегистрировавшихся сегодня и вчера."""
    if not is_admin(message.from_user.id):
        return
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)

        def _age_from_str(bd: str) -> int | None:
            """Возвращает возраст из строки ДД.ММ.ГГГГ или None если не удалось распарсить."""
            try:
                dt = datetime.strptime(bd, "%d.%m.%Y").date()
                today = date.today()
                return (today - dt).days // 365
            except Exception:
                return None

        def _age_groups(ages: list[int]) -> str:
            if not ages:
                return "нет данных"
            groups = {"до 18": 0, "18–24": 0, "25–34": 0, "35–44": 0, "45–54": 0, "55+": 0}
            for a in ages:
                if a < 18:
                    groups["до 18"] += 1
                elif a <= 24:
                    groups["18–24"] += 1
                elif a <= 34:
                    groups["25–34"] += 1
                elif a <= 44:
                    groups["35–44"] += 1
                elif a <= 54:
                    groups["45–54"] += 1
                else:
                    groups["55+"] += 1
            lines = [f"• {k}: {v}" for k, v in groups.items() if v > 0]
            avg = sum(ages) / len(ages)
            lines.append(f"\nСредний возраст: *{avg:.0f}*")
            return "\n".join(lines)

        blocks = []
        for label, start, end in [
            ("Сегодня", today_start, None),
            ("Вчера",   yesterday_start, today_start),
        ]:
            q = select(User.birth_date).where(
                User.birth_date.isnot(None),
                User.created_at >= start,
            )
            if end:
                q = q.where(User.created_at < end)
            rows = (await session.execute(q)).scalars().all()

            ages = [a for bd in rows if (a := _age_from_str(bd)) is not None]
            total = len(rows)
            with_age = len(ages)

            block = (
                f"📅 *{label}*\n"
                f"Новых с датой рождения: {with_age} / {total}\n"
                f"{_age_groups(ages)}"
            )
            blocks.append(block)

        await message.answer(
            "🎂 *Возраст новых пользователей*\n━━━━━━━━━━━━━━━\n\n"
            + "\n\n".join(blocks),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("cmd_ages error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── Сброс12 — сбросить сессию (доступно всем пользователям) ─────────────────

@router.message(F.text.lower() == "сброс12")
async def reset_session_admin(message: Message, user: User, session: AsyncSession):
    """Кодовое слово — сбрасывает профиль до состояния нового пользователя."""

    try:
        from aiogram.fsm.context import FSMContext
        from sqlalchemy import delete
        from bot.models.user import UserProfile, UsageLimits, Subscription

        # Очищаем только дату рождения (gender — NOT NULL, не трогаем)
        user.birth_date = None
        user.first_name = message.from_user.first_name or user.first_name

        # Сбрасываем профиль (онбординг, личность)
        result = await session.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = result.scalar_one_or_none()
        if profile:
            prefs = dict(profile.preferences or {})
            prefs.pop("onboarding_done", None)
            prefs.pop("onboarding_interest", None)
            prefs.pop("personality", None)
            profile.preferences = prefs

        # Удаляем лимиты (сбросятся до нуля при следующем использовании)
        await session.execute(delete(UsageLimits).where(UsageLimits.user_id == user.id))

        await session.commit()

        # Сбрасываем Redis-кеши для этого пользователя
        from bot.services.cache import get_redis
        r = await get_redis()
        await r.delete(f"sponsor_checked:{user.telegram_id}")
        await r.delete(f"kb_shown:{user.telegram_id}")
        await r.delete(f"menu_msg:{user.telegram_id}")

        await message.answer(
            "✅ *Сессия сброшена.*\n\n"
            "Профиль, дата рождения и лимиты очищены.\n"
            "Нажми /start — начнёшь как новый пользователь.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.exception("reset_session_admin error")
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")
