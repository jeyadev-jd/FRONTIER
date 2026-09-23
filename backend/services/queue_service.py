"""
FRONTIER Queue Service — auto-draft and approval queue management.

Pipeline:
  ANALYZED items above threshold → auto-draft → PENDING_APPROVAL
  Old DISCOVERED/ANALYZED items → EXPIRED
  PENDING_APPROVAL items → send to Discord for human review
"""
import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import AsyncSessionLocal
from backend.database.models import ContentItem, Post, ContentStatus, ContentCategory
from backend.config import get_settings

logger = structlog.get_logger()

# Items above this threshold get auto-drafted
AUTO_DRAFT_THRESHOLD = 0.72

# Items older than this without advancing get expired
EXPIRY_HOURS = {
    ContentStatus.DISCOVERED: 72,
    ContentStatus.ANALYZED: 48,
    ContentStatus.DRAFTED: 24,
}

# Max posts to auto-draft per run (don't flood the queue)
MAX_DRAFT_PER_RUN = 5


async def auto_draft_high_relevance(db: AsyncSession, threshold: float = AUTO_DRAFT_THRESHOLD) -> list[str]:
    """
    Find ANALYZED items above threshold, generate draft posts.
    Returns list of created Post IDs.
    """
    settings = get_settings()

    result = await db.execute(
        select(ContentItem)
        .where(
            ContentItem.status == ContentStatus.ANALYZED,
            ContentItem.overall_relevance >= threshold,
            ContentItem.category != ContentCategory.IGNORE,
        )
        .order_by(ContentItem.overall_relevance.desc())
        .limit(MAX_DRAFT_PER_RUN)
    )
    items = result.scalars().all()

    if not items:
        logger.info("queue.auto_draft.nothing_above_threshold", threshold=threshold)
        return []

    from backend.services.generation_service import generate_post
    created: list[str] = []

    for item in items:
        try:
            channel = item.recommended_channel or "#frontier-lounge"
            category = item.category.value if item.category else "GENERAL"

            extra_context = None
            if item.raw_content:
                extra_context = item.raw_content[:1500]

            post_data = await generate_post(
                topic=item.title or item.source_url or "content",
                channel=channel,
                category=category,
                source_url=item.source_url,
                extra_context=extra_context,
                db=db,
            )

            post = Post(
                content_item_id=item.id,
                channel=post_data["channel"],
                generated_content=post_data["content"],
                status=ContentStatus.PENDING_APPROVAL,
            )
            db.add(post)

            item.status = ContentStatus.DRAFTED
            await db.flush()

            created.append(post.id)
            logger.info("queue.auto_drafted", item_id=item.id[:8], channel=post.channel, score=item.overall_relevance)

            # Small pause between LLM calls
            await asyncio.sleep(1)

        except Exception as e:
            logger.error("queue.auto_draft.error", item_id=item.id[:8], error=str(e)[:100])
            item.status = ContentStatus.FAILED

    await db.commit()
    logger.info("queue.auto_draft.done", created=len(created))
    return created


async def expire_old_content(db: AsyncSession) -> int:
    """Mark stale content items as EXPIRED. Returns count expired."""
    now = datetime.now(timezone.utc)
    expired = 0

    for status, hours in EXPIRY_HOURS.items():
        cutoff = now - timedelta(hours=hours)
        result = await db.execute(
            select(ContentItem)
            .where(
                ContentItem.status == status,
                ContentItem.created_at < cutoff,
            )
        )
        items = result.scalars().all()
        for item in items:
            item.status = ContentStatus.EXPIRED
            expired += 1

    if expired:
        await db.commit()
        logger.info("queue.expire.done", expired=expired)

    return expired


async def get_pending_queue(db: AsyncSession, limit: int = 50) -> list[Post]:
    """Return posts awaiting approval, newest first."""
    result = await db.execute(
        select(Post)
        .where(Post.status == ContentStatus.PENDING_APPROVAL)
        .order_by(Post.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def notify_discord_pending(db: AsyncSession) -> int:
    """
    Send pending posts to Discord approval channel if bot is running.
    Returns count of notifications sent.
    """
    posts = await get_pending_queue(db, limit=10)
    if not posts:
        return 0

    try:
        from backend.services.discord_service import send_message
        sent = 0
        for post in posts[:3]:  # Max 3 per notification cycle
            preview = post.generated_content[:300] + ("…" if len(post.generated_content) > 300 else "")
            msg = (
                f"📬 **Pending Approval** | `{post.channel}`\n"
                f"Post ID: `{post.id[:8]}`\n"
                f"```\n{preview}\n```\n"
                f"Use `/frontier approve {post.id[:8]}` or review in dashboard."
            )
            await send_message("#frontier-guide", msg)
            sent += 1
            await asyncio.sleep(0.5)
        return sent
    except Exception as e:
        logger.warning("queue.notify_discord.failed", error=str(e)[:80])
        return 0


async def run_queue_cycle() -> dict:
    """Full queue maintenance cycle — call from scheduler."""
    logger.info("queue.cycle.start")
    async with AsyncSessionLocal() as db:
        drafted = await auto_draft_high_relevance(db)
        expired = await expire_old_content(db)

        # Apply auto-publish rules before notifying Discord
        from backend.services.autopublish_service import apply_auto_publish_rules
        auto_published = await apply_auto_publish_rules(db)

        notified = await notify_discord_pending(db)

    result = {"drafted": len(drafted), "expired": expired, "auto_published": auto_published, "notified": notified}
    logger.info("queue.cycle.done", **result)
    return result
