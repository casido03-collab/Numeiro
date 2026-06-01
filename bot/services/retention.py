"""Retention Push System — возврат неактивных пользователей."""
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ─── 30 push-сообщений (цикличная ротация) ───────────────────────────────────

RETENTION_PUSHES = [
    # Push #1
    "🔮 {name}, сегодня ваши энергии особенно нестабильны…\n"
    "Луна усиливает внутренние переживания, а это значит — ближайшие дни могут принести неожиданные разговоры и решения.\n"
    "Возможно именно сейчас вам нужен взгляд со стороны.\n"
    "Задайте любой вопрос Aisha — отношения, деньги, будущее: 👉 /start",

    # Push #2
    "🌙 {name}, некоторые знаки появляются в жизни не случайно.\n"
    "Ваша энергетика на этой неделе указывает на важные перемены, связанные с человеком, о котором вы думаете чаще обычного.\n"
    "Иногда судьба начинает менять всё постепенно.\n"
    "Спросите у Aisha то, что давно волнует: 👉 /start",

    # Push #3
    "✨ {name}, ваша интуиция сейчас сильнее чем обычно.\n"
    "Астрологические линии показывают период внутренних изменений и переоценки событий вокруг вас.\n"
    "Возможно ответы уже совсем рядом.\n"
    "Задайте вопрос Aisha: 👉 /start",

    # Push #4
    "🔮 {name}, ближайшие дни могут стать для вас переломными.\n"
    "Некоторые энергии вокруг вас начали меняться, особенно в сфере отношений и общения.\n"
    "Лучше узнать заранее, к чему это приведёт.\n"
    "Спросите у Aisha о своей ситуации: 👉 /start",

    # Push #5
    "🌌 {name}, сегодня особенно важно прислушиваться к внутренним ощущениям.\n"
    "Твоя энергия указывает на скрытые переживания, которые могут повлиять на ближайшие события.\n"
    "Иногда один ответ помогает увидеть всё иначе.\n"
    "👉 /start",

    # Push #6
    "💫 {name}, ваши числа судьбы сейчас активны как никогда.\n"
    "Есть вероятность неожиданной встречи или разговора, который изменит ваш взгляд на ситуацию.\n"
    "Хотите узнать подробнее?\n"
    "👉 /start",

    # Push #7
    "🔮 {name}, карты показывают напряжение между желаниями и реальностью.\n"
    "Такое состояние часто появляется перед важными переменами.\n"
    "Сейчас хороший момент чтобы задать вопрос о будущем.\n"
    "👉 /start",

    # Push #8
    "🌙 {name}, энергия этой недели связана с темой выбора.\n"
    "Некоторые решения, которые вы откладывали, скоро снова напомнят о себе.\n"
    "Aisha поможет разобраться в ситуации: 👉 /start",

    # Push #9
    "✨ {name}, ваша натальная энергия сейчас проходит фазу обновления.\n"
    "Это может отражаться на отношениях, настроении и даже случайных совпадениях вокруг.\n"
    "Хотите посмотреть глубже?\n"
    "👉 /start",

    # Push #10
    "🔮 {name}, иногда судьба начинает подавать знаки ещё до событий.\n"
    "Сегодня именно такой день.\n"
    "Спросите у Aisha всё что волнует: 👉 /start",

    # Push #11
    "🌌 {name}, последние дни ваша энергетика изменилась сильнее обычного.\n"
    "Особенно это касается сферы общения и личной жизни.\n"
    "Возможно пора взглянуть на ситуацию иначе.\n"
    "👉 /start",

    # Push #12
    "💫 {name}, сейчас вокруг вас формируется новый жизненный цикл.\n"
    "Некоторые события уже начинают двигаться в неожиданную сторону.\n"
    "Узнайте что ждёт вас дальше: 👉 /start",

    # Push #13
    "🌙 {name}, ваша интуиция пытается обратить внимание на что-то важное.\n"
    "Особенно в вопросах чувств и доверия.\n"
    "Aisha поможет прочитать эти знаки: 👉 /start",

    # Push #14
    "🔮 {name}, звёзды указывают на скрытую эмоциональную нагрузку.\n"
    "Возможно внутри вас давно есть вопрос, который не даёт покоя.\n"
    "Самое время получить ответ: 👉 /start",

    # Push #15
    "✨ {name}, ближайшие дни могут принести неожиданные новости.\n"
    "Энергетические линии сейчас особенно чувствительны к переменам.\n"
    "Хотите узнать, что ждёт впереди?\n"
    "👉 /start",

    # Push #16
    "🌌 {name}, иногда люди возвращаются к ответам именно тогда, когда готовы их услышать.\n"
    "Возможно этот момент настал и для вас.\n"
    "👉 /start",

    # Push #17
    "💫 {name}, ваша энергия сейчас особенно восприимчива к влиянию окружающих людей.\n"
    "Это может изменить планы и внутреннее состояние.\n"
    "Разберём подробнее? 👉 /start",

    # Push #18
    "🔮 {name}, карты показывают сильное влияние прошлого на ваши нынешние решения.\n"
    "Иногда важно понять причину происходящего.\n"
    "Спросите у Aisha: 👉 /start",

    # Push #19
    "🌙 {name}, сегодняшний день может стать важной точкой для новых решений.\n"
    "Некоторые события уже начали складываться вокруг вас.\n"
    "👉 /start",

    # Push #20
    "✨ {name}, сейчас особенно важно обращать внимание на совпадения и повторяющиеся знаки.\n"
    "Иногда судьба говорит именно через них.\n"
    "👉 /start",

    # Push #21
    "🔮 {name}, энергия вокруг вас становится всё более переменчивой.\n"
    "Это может повлиять на отношения, финансы и внутреннее состояние.\n"
    "Узнайте что ждёт впереди: 👉 /start",

    # Push #22
    "🌌 {name}, некоторые люди появляются в жизни не случайно.\n"
    "И сейчас ваши линии судьбы особенно связаны с темой отношений.\n"
    "👉 /start",

    # Push #23
    "💫 {name}, ваша неделя может пройти совсем иначе, если заранее увидеть важные знаки.\n"
    "Сейчас хороший момент чтобы заглянуть глубже.\n"
    "👉 /start",

    # Push #24
    "🌙 {name}, иногда даже один вопрос помогает изменить взгляд на всё происходящее.\n"
    "Возможно сегодня именно такой день.\n"
    "👉 /start",

    # Push #25
    "🔮 {name}, ближайшие дни принесут энергию перемен и новых разговоров.\n"
    "Особенно с человеком, о котором вы думаете чаще остальных.\n"
    "👉 /start",

    # Push #26
    "✨ {name}, ваши внутренние ощущения сейчас могут оказаться точнее любых советов.\n"
    "Aisha поможет понять, к чему они ведут.\n"
    "👉 /start",

    # Push #27
    "🌌 {name}, энергетика этой недели указывает на важный эмоциональный период.\n"
    "Лучше заранее понять, что именно готовит судьба.\n"
    "👉 /start",

    # Push #28
    "💫 {name}, иногда судьба начинает менять события незаметно.\n"
    "Но именно такие периоды потом оказываются самыми важными.\n"
    "👉 /start",

    # Push #29
    "🌙 {name}, ваша энергия сейчас находится между прошлым и новым этапом.\n"
    "Возможно впереди уже начинается что-то значимое.\n"
    "👉 /start",

    # Push #30
    "🔮 {name}, Aisha снова готова посмотреть ваши линии судьбы и раскрыть скрытые влияния этой недели.\n"
    "👉 /start",
]

TRIAL_UPSELL_TEXT = (
    "🌙 {name}, бабушка Aisha просила передать…\n\n"
    "Иногда человек уходит именно в тот момент, когда ответы начинают становиться особенно важными.\n\n"
    "Если внутри остались вопросы — возвращайся.\n\n"
    "✨ /start"
)


def _is_push_time() -> bool:
    """Проверить что сейчас разрешённое время для retention (10:00–22:00 МСК)."""
    msk_hour = (datetime.now(timezone.utc).hour + 3) % 24
    return 10 <= msk_hour < 22


def _is_trial_upsell_time() -> bool:
    """Разрешённое время для trial upsell (7:00–23:00 МСК)."""
    msk_hour = (datetime.now(timezone.utc).hour + 3) % 24
    return 7 <= msk_hour < 23


async def run_retention_pushes(bot: Bot, session: AsyncSession) -> None:
    """Найти неактивных 24ч+ пользователей и отправить им push."""
    if not _is_push_time():
        return

    from bot.models.user import User, UserActivity

    threshold = datetime.now(timezone.utc) - timedelta(hours=24)

    result = await session.execute(
        select(User, UserActivity)
        .join(UserActivity, UserActivity.user_id == User.id)
        .where(
            User.is_blocked == False,  # noqa: E712
            UserActivity.last_activity_at <= threshold,
            # Не слать повторно если уже слали менее 24ч назад
            (UserActivity.last_push_at == None) |  # noqa: E711
            (UserActivity.last_push_at <= threshold),
        )
    )
    rows = result.all()

    now = datetime.now(timezone.utc)
    for user, activity in rows:
        name = user.first_name or "друг"
        idx = activity.push_index % len(RETENTION_PUSHES)
        text = RETENTION_PUSHES[idx].format(name=name)

        try:
            await bot.send_message(user.telegram_id, text, parse_mode=None)
            activity.last_push_at = now
            activity.push_index = activity.push_index + 1
            await session.commit()
            logger.info("Retention push #%s sent to user %s", idx + 1, user.telegram_id)
        except Exception as e:
            logger.warning("Retention push failed for user %s: %s", user.telegram_id, e)


async def run_trial_upsell(bot: Bot, session: AsyncSession) -> None:
    """Отправить trial upsell один раз — free-пользователям после 1ч неактивности."""
    if not _is_trial_upsell_time():
        return

    from bot.models.user import User, UserActivity, Subscription, PlanEnum, SubscriptionStatusEnum

    threshold = datetime.now(timezone.utc) - timedelta(hours=1)

    result = await session.execute(
        select(User, UserActivity)
        .join(UserActivity, UserActivity.user_id == User.id)
        .join(Subscription, Subscription.user_id == User.id)
        .where(
            User.is_blocked == False,  # noqa: E712
            Subscription.plan == PlanEnum.free,
            UserActivity.trial_upsell_sent == False,  # noqa: E712
            UserActivity.last_activity_at != None,  # noqa: E711  — был в боте хотя бы раз
            UserActivity.last_activity_at <= threshold,
        )
    )
    rows = result.all()

    for user, activity in rows:
        name = user.first_name or "друг"
        text = TRIAL_UPSELL_TEXT.format(name=name)
        try:
            await bot.send_message(user.telegram_id, text, parse_mode="HTML")
            activity.trial_upsell_sent = True
            await session.commit()
            logger.info("Trial upsell sent to user %s", user.telegram_id)
        except Exception as e:
            logger.warning("Trial upsell failed for user %s: %s", user.telegram_id, e)
            # Помечаем как отправленный даже при ошибке парсинга — иначе будет бесконечный retry
            if "can't parse entities" in str(e):
                activity.trial_upsell_sent = True
                await session.commit()
