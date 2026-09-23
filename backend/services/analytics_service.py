"""FRONTIER Analytics — content funnel stats and activity summaries."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ContentItem, Post, ContentStatus, ContentCategory


async def get_funnel_stats(db: AsyncSession, days: int = 7) -> dict:
    """Content funnel: discovered → analyzed → drafted → published."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async def count(model, *conditions):
        result = await db.execute(select(func.count()).where(*conditions))
        return result.scalar() or 0

    total_discovered = await count(ContentItem, ContentItem.created_at >= since)
    analyzed = await count(ContentItem, ContentItem.created_at >= since, ContentItem.status.in_([
        ContentStatus.ANALYZED, ContentStatus.DRAFTED, ContentStatus.PENDING_APPROVAL,
        ContentStatus.APPROVED, ContentStatus.PUBLISHED,
    ]))
    drafted = await count(ContentItem, ContentItem.created_at >= since, ContentItem.status.in_([
        ContentStatus.DRAFTED, ContentStatus.PENDING_APPROVAL,
        ContentStatus.APPROVED, ContentStatus.PUBLISHED,
    ]))
    pending = await count(Post, Post.status == ContentStatus.PENDING_APPROVAL)
    published = await count(Post, Post.status == ContentStatus.PUBLISHED, Post.created_at >= since)
    rejected = await count(Post, Post.status == ContentStatus.REJECTED, Post.created_at >= since)
    expired = await count(ContentItem, ContentItem.created_at >= since, ContentItem.status == ContentStatus.EXPIRED)
    duplicates = await count(ContentItem, ContentItem.created_at >= since, ContentItem.status == ContentStatus.DUPLICATE)

    return {
        "period_days": days,
        "discovered": total_discovered,
        "analyzed": analyzed,
        "drafted": drafted,
        "pending_approval": pending,
        "published": published,
        "rejected": rejected,
        "expired": expired,
        "duplicates_blocked": duplicates,
        "publish_rate": round(published / max(drafted, 1), 2),
        "duplicate_rate": round(duplicates / max(total_discovered + duplicates, 1), 2),
    }


async def get_category_breakdown(db: AsyncSession, days: int = 30) -> list[dict]:
    """Count published posts per category."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(ContentItem.category, func.count().label("count"))
        .where(ContentItem.created_at >= since)
        .group_by(ContentItem.category)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return [{"category": (r.category.value if r.category else "UNKNOWN"), "count": r.count} for r in rows]


async def get_channel_breakdown(db: AsyncSession, days: int = 30) -> list[dict]:
    """Count published posts per channel."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Post.channel, func.count().label("count"))
        .where(Post.status == ContentStatus.PUBLISHED, Post.created_at >= since)
        .group_by(Post.channel)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return [{"channel": r.channel, "count": r.count} for r in rows]


async def get_daily_activity(db: AsyncSession, days: int = 14) -> list[dict]:
    """Daily discovered + published counts for sparkline."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    disc_result = await db.execute(
        select(
            func.date(ContentItem.created_at).label("day"),
            func.count().label("discovered")
        )
        .where(ContentItem.created_at >= since)
        .group_by(func.date(ContentItem.created_at))
        .order_by(func.date(ContentItem.created_at))
    )
    disc_rows = {str(r.day): r.discovered for r in disc_result.all()}

    pub_result = await db.execute(
        select(
            func.date(Post.created_at).label("day"),
            func.count().label("published")
        )
        .where(Post.status == ContentStatus.PUBLISHED, Post.created_at >= since)
        .group_by(func.date(Post.created_at))
        .order_by(func.date(Post.created_at))
    )
    pub_rows = {str(r.day): r.published for r in pub_result.all()}

    days_out = []
    for i in range(days):
        d = (since + timedelta(days=i)).strftime("%Y-%m-%d")
        days_out.append({
            "date": d,
            "discovered": disc_rows.get(d, 0),
            "published": pub_rows.get(d, 0),
        })
    return days_out


async def get_top_content(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Highest-scoring recent content items."""
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.overall_relevance.isnot(None))
        .order_by(ContentItem.overall_relevance.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        {
            "id": ci.id[:8],
            "title": ci.title,
            "url": ci.source_url,
            "score": ci.overall_relevance,
            "category": ci.category.value if ci.category else None,
            "channel": ci.recommended_channel,
            "status": ci.status.value if ci.status else None,
        }
        for ci in items
    ]
