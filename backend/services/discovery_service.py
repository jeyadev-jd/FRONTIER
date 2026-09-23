"""
Content discovery orchestrator.

Pipeline:
  search → extract → analyze → score → deduplicate → classify → save as ContentItem
"""
import asyncio
import structlog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.search_service import search_web, search_hackathons, search_research
from backend.services.arxiv_service import get_recent_ai_papers
from backend.services.extraction_service import extract_content
from backend.services.relevance_service import (
    classify_content,
    score_relevance,
    passes_quality_gate,
)
from backend.services.duplicate_service import check_duplicate, compute_hashes
from backend.services.style_service import get_channel_for_category
from backend.database.models import ContentItem, ContentStatus, ContentCategory
from backend.config import get_settings

logger = structlog.get_logger()

DISCOVERY_QUERIES = {
    "AI": [
        "new AI tool open source 2025",
        "LLM fine-tuning tutorial 2025",
        "local LLM model released",
        "AI agent framework release",
        "vibe coding AI tool",
    ],
    "BUILD": [
        "open source developer tool github 2025",
        "new python library released",
        "fastapi tutorial project",
        "react typescript tutorial project",
    ],
    "RESEARCH": [
        "machine learning paper breakthrough",
        "AI research paper 2025",
        "NLP paper released",
    ],
    "HACKATHON": [
        "student hackathon registration open 2025 2026",
        "AI hackathon deadline 2025",
        "devpost hackathon open",
    ],
    "OPPORTUNITY": [
        "AI student internship 2025 application open",
        "research fellowship students AI 2025",
    ],
}


async def _process_result(
    db: AsyncSession,
    item: dict,
    category: str,
    settings,
) -> ContentItem | None:
    """Full pipeline for a single discovered item. Returns saved ContentItem or None."""
    url = item.get("url", "")
    title = item.get("title", "") or ""
    snippet = item.get("snippet", "") or ""

    if not url or not url.startswith(("http://", "https://")):
        return None

    # Extract full content
    extracted = await extract_content(url, max_chars=3000)
    text = extracted.get("text") or snippet
    canonical_title = extracted.get("title") or title

    if not text:
        return None

    # Compute hashes for dedup
    hashes = compute_hashes(canonical_title, text, url)

    # Duplicate check
    dup = await check_duplicate(
        db,
        url=url,
        title=canonical_title,
        content_hash=hashes["content_hash"],
    )
    if dup["is_duplicate"]:
        logger.debug("discovery.duplicate", url=url[:60], reason=dup["reason"])
        return None

    # Score relevance
    scores = score_relevance(text=text, title=canonical_title, url=url)

    # Quality gate
    if not passes_quality_gate(
        scores,
        min_relevance=settings.min_relevance_score,
        min_credibility=settings.min_credibility_score,
    ):
        logger.debug(
            "discovery.below_threshold",
            url=url[:60],
            overall=scores["overall"],
            credibility=scores["credibility"],
        )
        return None

    # Classify
    detected_category = classify_content(text, canonical_title)
    if detected_category == "IGNORE":
        return None

    final_category = detected_category if detected_category != "GENERAL" else category

    try:
        cat_enum = ContentCategory(final_category)
    except ValueError:
        cat_enum = ContentCategory.GENERAL

    channel = get_channel_for_category(final_category)

    content_item = ContentItem(
        source_url=url,
        canonical_url=hashes["canonical_url"],
        title=canonical_title[:500],
        raw_content=text[:8000],
        content_hash=hashes["content_hash"],
        title_hash=hashes["title_hash"],
        category=cat_enum,
        status=ContentStatus.ANALYZED,
        relevance_scores=scores,
        overall_relevance=scores["overall"],
        credibility_score=scores["credibility"],
        recommended_channel=channel,
    )
    db.add(content_item)
    await db.commit()
    await db.refresh(content_item)

    logger.info(
        "discovery.saved",
        id=content_item.id[:8],
        channel=channel,
        score=scores["overall"],
        title=canonical_title[:60],
    )
    return content_item


async def discover_by_category(
    db: AsyncSession,
    category: str,
    max_items: int = 20,
) -> list[ContentItem]:
    """Run discovery for a specific category. Returns list of new ContentItems."""
    settings = get_settings()
    queries = DISCOVERY_QUERIES.get(category.upper(), [])
    saved = []

    for query in queries:
        if len(saved) >= max_items:
            break

        if category.upper() == "RESEARCH":
            results = await search_research(query, max_results=8)
        elif category.upper() == "HACKATHON":
            results = await search_hackathons(max_results=8)
        else:
            results = await search_web(query, max_results=8)

        for item in results:
            if len(saved) >= max_items:
                break
            try:
                ci = await _process_result(db, item, category, settings)
                if ci:
                    saved.append(ci)
            except Exception as e:
                logger.warning("discovery.item_error", error=str(e)[:100])
            await asyncio.sleep(0.5)  # polite crawl rate

    return saved


async def discover_ai_papers(db: AsyncSession, max_items: int = 10) -> list[ContentItem]:
    """Discover recent AI papers from arXiv."""
    settings = get_settings()
    papers = await get_recent_ai_papers(max_results=max_items * 2)
    saved = []

    for paper in papers:
        if len(saved) >= max_items:
            break
        try:
            ci = await _process_result(db, paper, "RESEARCH", settings)
            if ci:
                saved.append(ci)
        except Exception as e:
            logger.warning("discovery.paper_error", error=str(e)[:100])
        await asyncio.sleep(0.3)

    return saved


async def run_full_discovery(db: AsyncSession) -> dict:
    """Run a full discovery cycle across all categories."""
    logger.info("discovery.full_cycle.start")
    results = {}

    for category in ["AI", "BUILD", "RESEARCH", "HACKATHON", "OPPORTUNITY"]:
        items = await discover_by_category(db, category, max_items=5)
        results[category] = len(items)
        await asyncio.sleep(2)

    # Also grab arXiv papers
    papers = await discover_ai_papers(db, max_items=5)
    results["ARXIV_PAPERS"] = len(papers)

    total = sum(results.values())
    logger.info("discovery.full_cycle.complete", total=total, breakdown=results)
    return results
