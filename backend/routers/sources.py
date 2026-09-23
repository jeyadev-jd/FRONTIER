"""Source management API — RSS feeds, X searches, web queries."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from backend.database.db import get_db
from backend.database.models import Source, SourceType, ContentCategory
from backend.services.rss_service import DEFAULT_FEEDS

logger = structlog.get_logger()
router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    source_type: str
    url: str | None = None
    query: str | None = None
    category: str = "GENERAL"
    is_enabled: bool = True
    config: dict | None = None


@router.get("")
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    sources = result.scalars().all()

    # Include built-in defaults even if not yet in DB
    builtin = [
        {
            "id": f"builtin-{k}",
            "name": v["label"],
            "source_type": "RSS",
            "url": v["url"],
            "category": v["category"],
            "is_enabled": True,
            "builtin": True,
            "last_fetched": None,
        }
        for k, v in DEFAULT_FEEDS.items()
    ]

    custom = [
        {
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type.value if s.source_type else None,
            "url": s.url,
            "query": s.query,
            "category": s.category.value if s.category else None,
            "is_enabled": s.is_enabled,
            "last_fetched": str(s.last_fetched) if s.last_fetched else None,
            "fetch_count": s.fetch_count,
            "error_count": s.error_count,
            "builtin": False,
        }
        for s in sources
    ]

    return {"builtin": builtin, "custom": custom}


@router.post("")
async def create_source(req: SourceCreate, db: AsyncSession = Depends(get_db)):
    valid_types = [t.value for t in SourceType]
    if req.source_type.upper() not in valid_types:
        raise HTTPException(status_code=400, detail=f"source_type must be one of {valid_types}")

    try:
        cat = ContentCategory(req.category.upper())
    except ValueError:
        cat = ContentCategory.GENERAL

    source = Source(
        name=req.name,
        source_type=SourceType(req.source_type.upper()),
        url=req.url,
        query=req.query,
        category=cat,
        is_enabled=req.is_enabled,
        config=req.config,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {"id": source.id, "name": source.name, "status": "created"}


@router.post("/{source_id}/toggle")
async def toggle_source(source_id: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_enabled = not source.is_enabled
    await db.commit()
    return {"id": source_id, "is_enabled": source.is_enabled}


@router.delete("/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"deleted": source_id}


@router.post("/{source_id}/fetch")
async def fetch_source_now(source_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger a fetch for a custom source."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from datetime import datetime, timezone
    from backend.services.discovery_service import _process_result
    from backend.config import get_settings

    settings = get_settings()
    items: list[dict] = []

    if source.source_type == SourceType.RSS and source.url:
        from backend.services.rss_service import fetch_feed
        items = await fetch_feed(source.url, max_items=15)
        for item in items:
            item["category"] = source.category.value if source.category else "GENERAL"

    elif source.source_type == SourceType.X and source.query:
        from backend.services.x_service import search_x
        items = await search_x(source.query, max_results=20)

    elif source.source_type == SourceType.WEB_SEARCH and source.query:
        from backend.services.search_service import search_web
        items = await search_web(source.query, max_results=15)

    saved = 0
    for item in items:
        try:
            ci = await _process_result(db, item, source.category.value if source.category else "GENERAL", settings)
            if ci:
                saved += 1
        except Exception:
            pass

    source.last_fetched = datetime.now(timezone.utc)
    source.fetch_count += 1
    await db.commit()

    return {"fetched": len(items), "saved": saved, "source": source.name}
