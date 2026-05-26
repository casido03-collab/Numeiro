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
        total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0

        active_subs = (await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatusEnum.active,
                Subscription.plan != PlanEnum.free,
            )
        )).scalar() or 0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        today_revenue = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= today_start,
            )
        )).scalar() or 0

        month_revenue = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "completed",
                Payment.created_at >= month_start,
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

        plan_counts = {}
        for plan in PlanEnum:
            count = (await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.plan == plan,
                    Subscription.status == SubscriptionStatusEnum.active,
                )
            )).scalar() or 0
            plan_counts[plan.value] = count

        text = (
            f"📊 *Статистика Aisha AI*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"👥 Всего пользователей: *{total_users}*\n"
            f"💎 Активных подписок: *{active_subs}*\n\n"
            f"📋 *По тарифам:*\n"
            f"• Free: {plan_counts.get('free', 0)}\n"
            f"• Lite: {plan_counts.get('lite', 0)}\n"
            f"• Premium: {plan_counts.get('premium', 0)}\n"
            f"• Pro: {plan_counts.get('pro', 0)}\n\n"
            f"💰 *Доход:*\n"
            f"• Сегодня: {today_revenue} ₽\n"
            f"• Месяц: {month_revenue} ₽\n\n"
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

        payments_total = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.user_id == user.id, Payment.status == "completed"
            )
        )).scalar() or 0

        plan = sub.plan.value if sub else "free"
        status = sub.status.value if sub else "—"
        expires = sub.expires_at.strftime("%d.%m.%Y") if (sub and sub.expires_at) else "—"
        created = user.created_at.strftime("%d.%m.%Y %H:%M") if user.created_at else "—"

        text = (
            f"👤 *Пользователь \\#{user.id}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Telegram ID: `{user.telegram_id}`\n"
            f"Имя: {user.first_name or '—'}\n"
            f"Username: @{user.username or '—'}\n"
            f"Дата рождения: {user.birth_date or '—'}\n\n"
            f"📋 *Тариф:* {plan}\n"
            f"Статус: {status}\n"
            f"Истекает: {expires}\n\n"
            f"💰 Оплачено: {payments_total} ₽\n"
            f"🤖 AI запросов: {ai_requests}\n"
            f"💸 AI расходы: ${ai_cost:.4f}\n\n"
            f"Зарегистрирован: {created}"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("cmd_user error")
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
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        top_users = await session.execute(
            select(UsageLimits.user_id, UsageLimits.ai_messages, User.first_name, User.telegram_id)
            .join(User, User.id == UsageLimits.user_id)
            .where(UsageLimits.period_start == today)
            .order_by(UsageLimits.ai_messages.desc())
            .limit(10)
        )
        rows = top_users.all()

        if not rows:
            await message.answer(f"📊 *Топ за сегодня ({today}):*\n\nНет данных", parse_mode="Markdown")
            return

        lines = []
        for i, (uid, msgs, name, tg_id) in enumerate(rows, 1):
            label = name or f"id{tg_id}"
            lines.append(f"{i}. {label} (`{tg_id}`): *{msgs}* AI-сообщений")

        await message.answer(
            f"📊 *Топ пользователей за {today}:*\n\n" + "\n".join(lines),
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
