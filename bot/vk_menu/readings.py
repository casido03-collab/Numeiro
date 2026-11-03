"""Use the same calculations, prompts and paid-result ledger as Telegram."""
from datetime import datetime, timedelta, timezone
import json
import random
from sqlalchemy import select
from bot.models.user import UserReport, PaidResult
from bot.services import numerology, matrix
from bot.services.compatibility import calculate_compatibility
from bot.services.dates import find_favorable_dates
from bot.services.fulfillment import generate_paid_report, result_key
from bot.services.question_context import recent_questions
from bot.services.reports_service import save_report
from bot.services.ai_service import generate
from bot.prompts import prompts
from bot.utils import parse_birth_date
from bot.handlers.reading import SPHERE_NAMES
from bot.handlers.compatibility import RELATION_NAMES
from bot.handlers.dates import EVENT_NAMES
from bot.handlers.tarot import MAJOR_ARCANA
from bot.handlers.weekly import _week_energy
from bot.handlers.daily import _day_number

MSK = timezone(timedelta(hours=3))
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def today():
    return datetime.now(MSK).date()


async def build_details(session, user, product, data, request_id):
    birth = parse_birth_date(user.birth_date)
    if birth is None:
        raise ValueError("Birth date required")
    day = today()
    nums = numerology.calculate_all(birth)
    context = {"name": user.first_name or "друг", "birth_date": user.birth_date}
    meta = {}
    if product == "personal_question":
        question = data["question"]
        context.update(question=question, numbers={k:v for k,v in nums.items() if k in ("life_path", "destiny", "personality")},
                       recent_conversation=await recent_questions(session, user.id), request_id=f"vk:{request_id}")
        title, report_type = f"Вопрос: {question[:70]}", "personal_question"
        meta = {"question": question}
    elif product == "mini_reading":
        sphere = data["sphere"]
        context.update(sphere=SPHERE_NAMES[sphere], numbers=nums, traits=numerology.get_traits(nums["life_path"]))
        title, report_type = f"Разбор: {SPHERE_NAMES[sphere]}", "mini_report"
        meta = {"sphere": sphere, "birth_date": user.birth_date}
    elif product == "full_matrix":
        context.update(matrix=matrix.matrix_to_context(matrix.calculate_matrix(birth)), numbers=nums)
        title, report_type = "Матрица судьбы", "destiny_matrix"
    elif product == "tarot_card":
        key, card_name, label = random.Random(user.id*1000+day.toordinal()).choice(MAJOR_ARCANA)
        context.update(card=label, card_name=card_name, numbers=nums, date=day.isoformat())
        title, report_type = f"Карта дня — {label} | {day:%d.%m.%Y}", "tarot_card"
        meta = {"card_key": key, "card_name": card_name, "date": day.isoformat()}
    elif product == "weekly_report":
        end = day + timedelta(days=6)
        context.update(sphere=SPHERE_NAMES[data["sphere"]], numbers=nums,
                       week_start=f"{day:%d.%m.%Y}", week_end=f"{end:%d.%m.%Y}", week_energy=_week_energy(birth, day),
                       days=[{"date": f"{day+timedelta(days=i):%d.%m}", "weekday": WEEKDAYS[(day+timedelta(days=i)).weekday()]} for i in range(7)])
        title, report_type = f"Неделя {day:%d.%m}–{end:%d.%m}", "weekly_forecast"
        meta = {"sphere": data["sphere"], "week_start": str(day), "week_end": str(end)}
    elif product == "compatibility":
        partner = parse_birth_date(data["partner_date"])
        relation = data["relation"]
        context = {"name": context["name"], "user_birth": user.birth_date,
                   "partner_birth": data["partner_date"], "relation_type": RELATION_NAMES[relation],
                   "compatibility": calculate_compatibility(birth, partner, relation)}
        title, report_type = f"Совместимость | {RELATION_NAMES[relation]}", "compatibility"
        meta = {"partner_birth": data["partner_date"], "relation_type": relation}
    elif product == "date_selection":
        event, days, mode = data["event"], int(data["days"]), data["weekdays"]
        favorable = find_favorable_dates(event, day, count=5, to_date=day+timedelta(days=days), weekdays=mode, birth_date=birth)
        context.update(event=EVENT_NAMES[event],
                       dates=[{**{k:d[k] for k in ("date", "energy", "personal_energy")}, "weekday": WEEKDAYS[d["weekday"]]} for d in favorable],
                       period_start=(day+timedelta(days=1)).isoformat(), period_end=(day+timedelta(days=days)).isoformat(), available_days=mode)
        title, report_type = f"Подбор дат: {EVENT_NAMES[event]}", "date_selection"
        meta = {"event": event, "period_start": context["period_start"], "period_end": context["period_end"]}
    else:
        raise ValueError("Unknown product")
    return {"context": context, "title": title, "report_type": report_type, "metadata": meta}


PROMPTS = {
    "personal_question": (prompts.PERSONAL_QUESTION_PAID_PROMPT, 2400),
    "mini_reading": (prompts.PAID_MINI_REPORT_PROMPT, 2000),
    "full_matrix": (prompts.FULL_MATRIX_PROMPT, 4200),
    "tarot_card": (prompts.TAROT_CARD_PROMPT, 2000),
    "weekly_report": (prompts.WEEKLY_PREDICTION_PROMPT, 3200),
    "compatibility": (prompts.COMPATIBILITY_PROMPT, 2800),
    "date_selection": (prompts.DATE_SELECTION_PROMPT, 2400),
}


async def cached_report(session, user_id, product, details):
    result = await session.get(PaidResult, result_key(user_id, product, "ru", details["context"]))
    return await session.get(UserReport, result.report_id) if result and result.report_id else None


async def fulfill(session, order):
    if order.report_id:
        return await session.get(UserReport, order.report_id)
    spec = order.details
    prompt, tokens = PROMPTS[order.product]
    result = await generate_paid_report(session, order.user_id, order.product, spec["report_type"], spec["title"],
        spec["context"], prompt("ru"), "ru", complexity="complex" if order.product == "full_matrix" else "medium",
        max_tokens=tokens, metadata=spec["metadata"])
    order.report_id, order.status = result.id, "fulfilled"
    await session.commit()
    return result


async def daily_report(session, user, kind):
    day = today()
    # The first result of the day stays available even after profile edits.
    rows = (await session.scalars(select(UserReport).where(UserReport.user_id == user.id,
        UserReport.report_type == kind).order_by(UserReport.id.desc()).limit(20))).all()
    for report in rows:
        if (report.metadata_json or {}).get("date") == day.isoformat():
            return report
    birth = parse_birth_date(user.birth_date)
    if kind == "horoscope":
        from bot.handlers.horoscope import HOROSCOPE_TEMPLATES, MYSTICAL_PHRASES, get_zodiac
        rng = random.Random(user.id*31337+day.toordinal())
        emoji, zodiac = get_zodiac(birth.day, birth.month)
        content = f"{emoji} {zodiac}\n\n{rng.choice(HOROSCOPE_TEMPLATES)} {rng.choice(MYSTICAL_PHRASES)}"
        title = f"Гороскоп {day:%d.%m.%Y}"
    else:
        nums = numerology.calculate_all(birth)
        context = {"name": user.first_name, "date": f"{day:%d.%m.%Y}", "weekday": WEEKDAYS[day.weekday()],
                   "day_number": _day_number(birth, day), "numbers": {k:v for k,v in nums.items() if k in ("life_path", "destiny", "personality")}}
        content = await generate(session, user.id, "daily_forecast", prompts.DAILY_FORECAST_PROMPT("ru"),
                                 json.dumps(context, ensure_ascii=False), complexity="simple", max_tokens=1200)
        title = f"Энергия дня {day:%d.%m.%Y}"
    report = await save_report(session, user.id, kind, title, content, {"date": day.isoformat(), "lang": "ru"})
    await session.commit()
    return report
