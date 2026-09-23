"""Approval queue API — manage pending posts."""
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from backend.database.db import get_db
from backend.database.models import Post, ContentItem, ContentStatus
from backend.services.queue_service import (
    auto_draft_high_relevance, expire_old_content, run_queue_cycle, get_pending_queue, AUTO_DRAFT_THRESHOLD
)

logger = structlog.get_logger()
router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("")
async def list_pending(limit: int = 50, db: AsyncSession = Depends(get_db)):
    posts = await get_pending_queue(db, limit=limit)
    out = []
    for p in posts:
        ci = None
        if p.content_item_id:
            ci = await db.get(ContentItem, p.content_item_id)
        out.append({
            "id": p.id,
            "channel": p.channel,
            "content": p.generated_content,
            "status": p.status.value,
            "created_at": str(p.created_at),
            "source_url": ci.source_url if ci else None,
            "source_title": ci.title if ci else None,
            "relevance": ci.overall_relevance if ci else None,
            "category": ci.category.value if ci and ci.category else None,
        })
    return out


@router.get("/stats")
async def queue_stats(db: AsyncSession = Depends(get_db)):
    from backend.services.analytics_service import get_funnel_stats
    return await get_funnel_stats(db, days=7)


@router.post("/run-cycle")
async def trigger_queue_cycle(background_tasks: BackgroundTasks):
    """Run auto-draft + expiry cycle in background."""
    background_tasks.add_task(run_queue_cycle)
    return {"status": "started"}


@router.post("/run-cycle-sync")
async def trigger_queue_cycle_sync():
    """Run auto-draft + expiry cycle synchronously."""
    result = await run_queue_cycle()
    return result


@router.post("/auto-draft")
async def trigger_auto_draft(threshold: float = AUTO_DRAFT_THRESHOLD, db: AsyncSession = Depends(get_db)):
    """Immediately draft high-relevance discovered content."""
    created = await auto_draft_high_relevance(db, threshold=threshold)
    return {"drafted": len(created), "post_ids": [p[:8] for p in created]}


@router.post("/expire")
async def trigger_expiry(db: AsyncSession = Depends(get_db)):
    """Expire stale content items."""
    expired = await expire_old_content(db)
    return {"expired": expired}
