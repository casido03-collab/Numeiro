"""Reports service — save and retrieve user reading history."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from bot.models.user import UserReport

logger = logging.getLogger(__name__)

FREE_LIMIT = 3
PAGE_SIZE = 5


def _make_preview(content: str, length: int = 300) -> str:
    text = content.strip()
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "…"


async def save_report(
    session: AsyncSession,
    user_id: int,
    report_type: str,
    title: str,
    content: str,
    metadata: dict | None = None,
) -> UserReport:
    """Add a report to user history. Caller is responsible for commit."""
    report = UserReport(
        user_id=user_id,
        report_type=report_type,
        title=title,
        short_preview=_make_preview(content),
        content=content,
        metadata_json=metadata or {},
    )
    session.add(report)
    return report


async def get_user_reports(
    session: AsyncSession,
    user_id: int,
    report_type: str,
    limit: int = PAGE_SIZE,
    offset: int = 0,
) -> list[UserReport]:
    result = await session.execute(
        select(UserReport)
        .where(UserReport.user_id == user_id, UserReport.report_type == report_type)
        .order_by(desc(UserReport.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_reports(
    session: AsyncSession,
    user_id: int,
    report_type: str,
) -> int:
    result = await session.execute(
        select(func.count()).where(
            UserReport.user_id == user_id,
            UserReport.report_type == report_type,
        )
    )
    return result.scalar() or 0


async def get_report_by_id(
    session: AsyncSession,
    report_id: int,
    user_id: int,
) -> UserReport | None:
    result = await session.execute(
        select(UserReport).where(
            UserReport.id == report_id,
            UserReport.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_categories_with_counts(
    session: AsyncSession,
    user_id: int,
) -> dict[str, int]:
    """Return {report_type: count} only for types that have ≥1 record."""
    result = await session.execute(
        select(UserReport.report_type, func.count().label("cnt"))
        .where(UserReport.user_id == user_id)
        .group_by(UserReport.report_type)
    )
    return {row.report_type: row.cnt for row in result.all()}
