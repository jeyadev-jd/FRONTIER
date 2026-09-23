"""
FRONTIER Auto-Publish Rule Engine.

Rules stored in DB (table: auto_publish_rules).
Each rule: category + min_score + optional channel → auto-publish without human approval.

Safety:
  - All rules disabled by default.
  - #signal is never auto-publishable (hard block).
  - Each auto-published post written to AuditLog.
  - Max 3 auto-publishes per queue cycle.
"""
import structlog
from datetime import datetime, timezone
from sqlalchemy import select, Column, String, Float, Boolean, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import Base, AsyncSessionLocal
from backend.database.models import Post, ContentItem, ContentStatus, AuditLog

logger = structlog.get_logger()

# Channels that can NEVER be auto-published regardless of rules
BLOCKED_CHANNELS = {"#signal", "#missions"}

MAX_AUTO_PUBLISH_PER_CYCLE = 3


class AutoPublishRule(Base):
    __tablename__ = "auto_publish_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True)        # NULL = any category
    channel = Column(String, nullable=True)          # NULL = any channel
    min_score = Column(Float, nullable=False, default=0.90)
    is_enabled = Column(Boolean, default=False)     # Off by default
    created_at = Column(DateTime, server_default="(CURRENT_TIMESTAMP)")
    updated_at = Column(DateTime, server_default="(CURRENT_TIMESTAMP)")


async def get_rules(db: AsyncSession) -> list[AutoPublishRule]:
    result = await db.execute(
        select(AutoPublishRule).order_by(AutoPublishRule.min_score.desc())
    )
    return result.scalars().all()


async def seed_default_rules(db: AsyncSession):
    """Insert default rules (all disabled) if table is empty."""
    existing = await db.execute(select(AutoPublishRule).limit(1))
    if existing.scalars().first():
        return

    defaults = [
        AutoPublishRule(name="high-confidence-ai",      category="AI",         channel="#neural",          min_score=0.92, is_enabled=False),
        AutoPublishRule(name="high-confidence-research", category="RESEARCH",   channel="#lab",             min_score=0.92, is_enabled=False),
        AutoPublishRule(name="hackathon-alerts",         category="HACKATHON",  channel="#arena",           min_score=0.88, is_enabled=False),
        AutoPublishRule(name="opportunity-alerts",       category="OPPORTUNITY",channel=None,               min_score=0.90, is_enabled=False),
        AutoPublishRule(name="build-showcase",           category="BUILD",      channel="#forge",           min_score=0.88, is_enabled=False),
        AutoPublishRule(name="any-very-high-score",      category=None,         channel=None,               min_score=0.95, is_enabled=False),
    ]
    for r in defaults:
        db.add(r)
    await db.commit()
    logger.info("autopublish.seeded_defaults", count=len(defaults))


def _post_matches_rule(post: Post, content_item: ContentItem | None, rule: AutoPublishRule) -> bool:
    if not rule.is_enabled:
        return False

    channel = post.channel or ""
    if channel in BLOCKED_CHANNELS:
        return False

    # Channel filter
    if rule.channel and rule.channel != channel:
        return False

    # Category filter
    if rule.category and content_item:
        item_cat = content_item.category.value if content_item.category else ""
        if item_cat != rule.category:
            return False

    # Score filter
    if content_item and content_item.overall_relevance is not None:
        if content_item.overall_relevance < rule.min_score:
            return False
    else:
        return False  # No score = can't auto-publish

    return True


async def apply_auto_publish_rules(db: AsyncSession) -> int:
    """
    Check PENDING_APPROVAL posts against enabled rules.
    Matching posts get published directly.
    Returns count of posts auto-published.
    """
    rules = await get_rules(db)
    enabled = [r for r in rules if r.is_enabled]
    if not enabled:
        return 0

    result = await db.execute(
        select(Post)
        .where(Post.status == ContentStatus.PENDING_APPROVAL)
        .order_by(Post.created_at.asc())
        .limit(MAX_AUTO_PUBLISH_PER_CYCLE * 3)  # fetch more, filter by rule
    )
    posts = result.scalars().all()
    if not posts:
        return 0

    published = 0
    for post in posts:
        if published >= MAX_AUTO_PUBLISH_PER_CYCLE:
            break

        content_item = None
        if post.content_item_id:
            content_item = await db.get(ContentItem, post.content_item_id)

        matched_rule = None
        for rule in enabled:
            if _post_matches_rule(post, content_item, rule):
                matched_rule = rule
                break

        if not matched_rule:
            continue

        # Publish
        try:
            from backend.services.discord_service import send_message
            ok = await send_message(post.channel, post.generated_content)
        except Exception as e:
            logger.warning("autopublish.discord_failed", post_id=post.id[:8], error=str(e)[:80])
            ok = False

        now = datetime.now(timezone.utc)
        if ok:
            post.status = ContentStatus.PUBLISHED
            post.published_at = now
            if content_item:
                content_item.status = ContentStatus.PUBLISHED

            # Audit log
            audit = AuditLog(
                action="AUTO_PUBLISHED",
                entity_id=post.id,
                entity_type="Post",
                output_status="ok",
                extra_data={
                    "rule": matched_rule.name,
                    "channel": post.channel,
                    "score": content_item.overall_relevance if content_item else None,
                    "category": content_item.category.value if content_item and content_item.category else None,
                },
            )
            db.add(audit)
            published += 1
            logger.info(
                "autopublish.published",
                post_id=post.id[:8],
                channel=post.channel,
                rule=matched_rule.name,
                score=content_item.overall_relevance if content_item else None,
            )
        else:
            logger.warning("autopublish.send_failed", post_id=post.id[:8])

    if published:
        await db.commit()

    return published
