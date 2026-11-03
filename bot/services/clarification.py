"""One included clarification for a personal question, within 24 hours."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from bot.models.user import UserReport
from bot.services.ai_service import generate
from bot.services.reports_service import save_report
from bot.prompts.prompts import CLARIFICATION_PROMPT
import json


class ClarificationUnavailable(ValueError):
    pass


def is_open(report):
    created = report.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= created + timedelta(hours=24)


async def clarify(session, user_id, report_id, question, lang):
    report = await session.scalar(select(UserReport).where(
        UserReport.id == report_id, UserReport.user_id == user_id,
        UserReport.report_type == "personal_question").with_for_update())
    if report is None or (report.metadata_json or {}).get("parent_report_id"):
        raise ClarificationUnavailable("not_found")
    metadata = report.metadata_json or {}
    if metadata.get("clarification_report_id"):
        return await session.get(UserReport, metadata["clarification_report_id"])
    if not is_open(report):
        raise ClarificationUnavailable("expired")
    content = await generate(session, user_id, "clarification", CLARIFICATION_PROMPT(lang),
        json.dumps({"original_question": metadata.get("question"), "original_answer": report.content,
                    "clarification": question}, ensure_ascii=False), max_tokens=1600)
    answer = await save_report(session, user_id, "personal_question", "Уточнение к личному вопросу",
                                content, {"parent_report_id": report_id, "question": question, "lang": lang})
    await session.flush()
    report.metadata_json = {**metadata, "clarification_report_id": answer.id}
    await session.commit()
    return answer
