"""Persist answers before debiting; resume interrupted settlement on the next update."""
import hashlib
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from bot.models.user import PaidResult, UserReport
from bot.services.ai_service import generate
from bot.services.limits import can_use_product, consume_product
from bot.services.reports_service import save_report

PROMPT_VERSION = "paid-v2"


class PurchaseRequired(RuntimeError):
    pass


def result_key(user_id, product, lang, context):
    # Telegram retries must remain the same order even if profile/history changes.
    if "request_id" in context:
        context = {"request_id": context["request_id"]}
    raw = json.dumps([PROMPT_VERSION, user_id, product, lang, context], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def settle(session, result_id):
    result = await session.scalar(select(PaidResult).where(PaidResult.id == result_id)
                                  .with_for_update().execution_options(populate_existing=True))
    if result.report_id is not None:
        return await session.get(UserReport, result.report_id)
    if not await consume_product(result.user_id, result.product_key, result.id):
        raise PurchaseRequired(result.product_key)
    report = await save_report(session, result.user_id, result.report_type,
                               result.title, result.content, result.metadata_json)
    await session.flush()
    result.report_id = report.id
    await session.commit()
    return report


async def recover_pending(session, user_id):
    ids = list((await session.scalars(select(PaidResult.id).where(
        PaidResult.user_id == user_id, PaidResult.report_id.is_(None)))).all())
    for result_id in ids:
        # Only complete a previously debited result. A new purchase must not be
        # silently spent on a stale, unpaid draft.
        from bot.services.cache import get_redis
        if await (await get_redis()).exists(f"spent:{result_id}"):
            await settle(session, result_id)


async def generate_paid_report(session, user_id, product, report_type, title,
                               context, prompt, lang="ru", complexity="medium",
                               max_tokens=2200, metadata=None):
    key = result_key(user_id, product, lang, context)
    result = await session.get(PaidResult, key)
    if result is None:
        if not await can_use_product(user_id, product):
            raise PurchaseRequired(product)
        content = await generate(session, user_id, product, prompt,
                                 json.dumps(context, ensure_ascii=False), complexity, max_tokens)
        result = PaidResult(id=key, user_id=user_id, product_key=product,
                            report_type=report_type, title=title[:255], content=content,
                            metadata_json={**(metadata or {}), "lang": lang, "prompt_version": PROMPT_VERSION})
        session.add(result)
        try:
            await session.commit()
        except IntegrityError:
            # Another concurrent update generated the same request first.
            await session.rollback()
    return await settle(session, key)
