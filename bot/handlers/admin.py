"""Команды администратора."""
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from bot.models.user import User, Subscription, Payment, AIRequest, PlanEnum, SubscriptionStatusEnum
from config import settings

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    total_users = (await session.execute(select(func.count(User.id)))).scalar()
    active_subs = (await session.execute(
        select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatusEnum.active,
            Subscription.plan != PlanEnum.free,
        )
    )).scalar()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_revenue = (await session.execute(
        select(func.sum(Payment.amount)).where(
            Payment.status == "completed",
            func.date(Payment.created_at) == today,
        )
    )).scalar() or 0

    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    month_revenue = (await session.execute(
        select(func.sum(Payment.amount)).where(
            Payment.status == "completed",
            Payment.created_at >= month_start,
        )
    )).scalar() or 0

    ai_cost_today = (await session.execute(
        select(func.sum(AIRequest.estimated_cost)).where(
            func.date(AIRequest.created_at) == today
        )
    )).scalar() or 0

    plan_counts = {}
    for plan in PlanEnum:
        count = (await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.plan == plan,
                Subscription.status == SubscriptionStatusEnum.active,
            )
        )).scalar()
        plan_counts[plan.value] = count

    text = f"""📊 *Статистика Aisha AI*
━━━━━━━━━━━━━━━
👥 Всего пользователей: *{total_users}*
💎 Активных подписок: *{active_subs}*

📋 *По тарифам:*
• Free: {plan_counts.get('free', 0)}
• Lite: {plan_counts.get('lite', 0)}
• Premium: {plan_counts.get('premium', 0)}
• Pro: {plan_counts.get('pro', 0)}

💰 *Доход:*
• Сегодня: {today_revenue} ⭐
• Месяц: {month_revenue} ⭐

🤖 *AI расходы сегодня:* ${ai_cost_today:.4f}"""

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("user"))
async def cmd_user(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /user <telegram_id>")
        return

    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный telegram_id")
        return

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
        select(func.sum(Payment.amount)).where(Payment.user_id == user.id, Payment.status == "completed")
    )).scalar() or 0

    text = f"""👤 *Пользователь #{user.id}*
━━━━━━━━━━━━━━━
Telegram ID: `{user.telegram_id}`
Имя: {user.first_name or '—'}
Username: @{user.username or '—'}
Дата рождения: {user.birth_date or '—'}
Реферал: {user.referral_code or '—'}

📋 *Подписка:* {sub.plan.value if sub else 'free'}
Статус: {sub.status.value if sub else '—'}
Истекает: {sub.expires_at.strftime('%d.%m.%Y') if sub and sub.expires_at else '—'}

💰 *Оплачено:* {payments_total} ⭐
🤖 *AI запросов:* {ai_requests}
💸 *AI расходы:* ${ai_cost:.4f}

Зарегистрирован: {user.created_at.strftime('%d.%m.%Y') if user.created_at else '—'}"""

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("grant"))
async def cmd_grant(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 4:
        await message.answer(
            "Использование: /grant <telegram_id> <plan> <days>\n"
            "days=0 → бессрочная подписка\n"
            "Пример: /grant 123456789 premium 30\n"
            "Пример: /grant 123456789 premium 0  (∞)",
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
        await message.answer("❌ Неверный план. Допустимые: free, lite, premium, pro")
        return

    result = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = result.scalar_one_or_none()
    if not user:
        await message.answer("❌ Пользователь не найден")
        return

    # days=0 → бессрочная (expires_at=None, автоистечение не сработает)
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
        user_msg = (
            f"🎁 *Тариф {plan_key.title()} активирован!*\n"
            + ("Доступ открыт бессрочно." if days == 0 else f"Доступ открыт на {days} дней.")
        )
        await message.bot.send_message(tg_id, user_msg, parse_mode="Markdown")
    except Exception:
        pass


@router.message(Command("costs"))
async def cmd_costs(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0)

    today_cost = (await session.execute(
        select(func.sum(AIRequest.estimated_cost)).where(func.date(AIRequest.created_at) == today)
    )).scalar() or 0

    month_cost = (await session.execute(
        select(func.sum(AIRequest.estimated_cost)).where(AIRequest.created_at >= month_start)
    )).scalar() or 0

    total_cost = (await session.execute(select(func.sum(AIRequest.estimated_cost)))).scalar() or 0

    by_model = await session.execute(
        select(AIRequest.model, func.count(AIRequest.id), func.sum(AIRequest.estimated_cost))
        .group_by(AIRequest.model)
    )

    model_stats = "\n".join(
        f"• {model}: {count} запросов, ${cost:.4f}"
        for model, count, cost in by_model
    )

    by_type = await session.execute(
        select(AIRequest.request_type, func.count(AIRequest.id))
        .group_by(AIRequest.request_type)
        .order_by(func.count(AIRequest.id).desc())
        .limit(10)
    )
    type_stats = "\n".join(f"• {t}: {c}" for t, c in by_type)

    await message.answer(
        f"💸 *AI Расходы*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Сегодня: ${today_cost:.4f}\n"
        f"Месяц: ${month_cost:.4f}\n"
        f"Всего: ${total_cost:.4f}\n\n"
        f"*По моделям:*\n{model_stats}\n\n"
        f"*Топ типов запросов:*\n{type_stats}",
        parse_mode="Markdown",
    )


@router.message(Command("limits"))
async def cmd_limits(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    from bot.models.user import UsageLimits
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    top_users = await session.execute(
        select(UsageLimits.user_id, UsageLimits.ai_messages)
        .where(UsageLimits.period_start == today)
        .order_by(UsageLimits.ai_messages.desc())
        .limit(10)
    )

    rows = "\n".join(f"• user_id={uid}: {msgs} AI-сообщений" for uid, msgs in top_users)
    await message.answer(
        f"📊 *Топ пользователей за сегодня:*\n{rows or 'Нет данных'}",
        parse_mode="Markdown",
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, session: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: /broadcast <текст сообщения>")
        return

    users = (await session.execute(
        select(User.telegram_id).where(User.is_blocked == False)
    )).scalars().all()

    sent = 0
    failed = 0
    for tg_id in users:
        try:
            await message.bot.send_message(tg_id, text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"✅ Рассылка завершена: отправлено {sent}, ошибок {failed}")
