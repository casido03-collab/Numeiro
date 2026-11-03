"""Small, user-owned conversation context; a reset affects future generation only."""
from datetime import datetime, timezone
from sqlalchemy import select
from bot.models.user import UserReport
from bot.services.cache import get_redis


async def recent_questions(session, user_id):
    r = await get_redis()
    cutoff = await r.get(f"question_context:after:{user_id}")
    query = select(UserReport).where(UserReport.user_id == user_id, UserReport.report_type == "personal_question")
    if cutoff:
        query = query.where(UserReport.created_at > datetime.fromtimestamp(float(cutoff), timezone.utc))
    reports = await session.scalars(query.order_by(UserReport.created_at.desc(), UserReport.id.desc()).limit(2))
    return [{"question": (report.metadata_json or {}).get("question", "")[:500],
             "previous_interpretation": report.content[:1400]} for report in reversed(list(reports))]
