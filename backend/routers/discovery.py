"""Discovery API routes."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from backend.database.db import get_db
from backend.database.models import ContentItem, ContentStatus
from backend.services import discovery_service, extraction_service, relevance_service

logger = structlog.get_logger()
router = APIRouter(prefix="/discovery", tags=["discovery"])


class DiscoverRequest(BaseModel):
    category: str = "AI"
    max_items: int = 10


class AnalyzeUrlRequest(BaseModel):
    url: str


@router.post("/run")
async def run_discovery(
    req: DiscoverRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger content discovery for a category. Runs in background."""
    valid = ["AI", "BUILD", "RESEARCH", "HACKATHON", "OPPORTUNITY", "ALL"]
    if req.category.upper() not in valid:
        raise HTTPException(status_code=400, detail=f"Category must be one of {valid}")

    if req.category.upper() == "ALL":
        background_tasks.add_task(discovery_service.run_full_discovery, db)
        return {"status": "started", "category": "ALL"}

    background_tasks.add_task(
        discovery_service.discover_by_category, db, req.category, req.max_items
    )
    return {"status": "started", "category": req.category}


@router.post("/analyze-url")
async def analyze_url(req: AnalyzeUrlRequest, db: AsyncSession = Depends(get_db)):
    """Extract and score content from a specific URL."""
    extracted = await extraction_service.extract_content(req.url)
    if not extracted.get("ok"):
        raise HTTPException(status_code=422, detail=extracted.get("error", "Extraction failed"))

    scores = relevance_service.score_relevance(
        text=extracted["text"],
        title=extracted["title"],
        url=req.url,
    )
    category = relevance_service.classify_content(extracted["text"], extracted["title"])

    return {
        "url": req.url,
        "canonical_url": extracted.get("canonical_url"),
        "title": extracted["title"],
        "word_count": extracted["word_count"],
        "text_preview": extracted["text"][:500],
        "category": category,
        "scores": scores,
        "passes_quality_gate": relevance_service.passes_quality_gate(scores),
    }


LISTING_PAGE_URLS = {
    "https://devpost.com/hackathons",
    "https://unstop.com/hackathons",
    "https://mlh.io/events",
    "https://devfolio.co/hackathons",
    "https://mlh.io/seasons/2026/events",
    "https://mlh.io/seasons/2025/events",
}


@router.get("/queue")
async def get_discovery_queue(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List analyzed content items waiting to become posts."""
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.status == ContentStatus.ANALYZED)
        .order_by(ContentItem.overall_relevance.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    return [
        {
            "id": ci.id,
            "title": ci.title,
            "url": ci.source_url,
            "category": ci.category.value if ci.category else None,
            "channel": ci.recommended_channel,
            "relevance": ci.overall_relevance,
            "credibility": ci.credibility_score,
            "scores": ci.relevance_scores,
            "created_at": ci.created_at,
        }
        for ci in items
        if (ci.source_url or "").rstrip("/") not in LISTING_PAGE_URLS
    ]


@router.post("/{item_id}/draft")
async def draft_from_discovery(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a post draft from a discovered content item."""
    item = await db.get(ContentItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    from backend.services.generation_service import generate_post
    from backend.database.models import Post
    import uuid

    result = await generate_post(
        topic=f"Title: {item.title}\n\nContent:\n{(item.raw_content or '')[:2000]}",
        channel=item.recommended_channel,
        category=item.category.value if item.category else "GENERAL",
        source_url=item.source_url,
    )

    post = Post(
        id=str(uuid.uuid4()),
        content_item_id=item.id,
        channel=result["channel"],
        generated_content=result["content"],
        status=ContentStatus.PENDING_APPROVAL,
    )
    db.add(post)
    item.status = ContentStatus.DRAFTED
    await db.commit()

    return {
        "post_id": post.id,
        "content": result["content"],
        "channel": result["channel"],
        "model": result["model"],
    }
