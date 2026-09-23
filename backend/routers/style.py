"""Style profile management API routes."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import structlog

from backend.database.db import get_db
from backend.database.models import StyleProfile, StyleExample
from backend.services.style_profile_service import (
    rebuild_profile,
    get_active_profile,
    analyze_style_examples,
    build_style_injection,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/style", tags=["style"])

VALID_CATEGORIES = ["ai", "research", "hackathons", "announcements", "general", "build", "debugging"]


class AddExampleRequest(BaseModel):
    content: str = Field(..., min_length=50, max_length=5000)
    category: str = Field("general")
    source_label: str | None = None


class ExampleResponse(BaseModel):
    id: str
    category: str
    content_preview: str
    source_label: str | None
    created_at: str


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Get the current active style profile."""
    profile = await get_active_profile(db)
    if not profile:
        return {
            "exists": False,
            "message": "No style profile yet. Add writing examples and call /style/rebuild.",
        }
    return {
        "exists": True,
        "id": profile.id,
        "name": profile.name,
        "tone": profile.tone,
        "sentence_length": profile.sentence_length,
        "technical_depth": profile.technical_depth,
        "humor_level": profile.humor_level,
        "emoji_usage": profile.emoji_usage,
        "formality": profile.formality,
        "vocabulary": profile.vocabulary,
        "structure": profile.structure,
        "preferred_expressions": profile.preferred_expressions,
        "things_to_avoid": profile.things_to_avoid,
        "full_attributes": profile.full_attributes,
        "example_count": profile.example_count,
        "updated_at": str(profile.updated_at),
    }


@router.post("/examples")
async def add_example(
    req: AddExampleRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a writing style example."""
    if req.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {VALID_CATEGORIES}")

    profile = await get_active_profile(db)

    example = StyleExample(
        profile_id=profile.id if profile else None,
        category=req.category,
        content=req.content,
        source_label=req.source_label,
    )
    db.add(example)
    await db.commit()
    await db.refresh(example)

    logger.info("style.example_added", category=req.category, id=example.id[:8])
    return {
        "id": example.id,
        "category": example.category,
        "content_preview": req.content[:100] + "...",
        "message": "Example added. Call /style/rebuild to update the profile.",
    }


@router.post("/examples/bulk")
async def add_examples_bulk(
    examples: list[AddExampleRequest],
    db: AsyncSession = Depends(get_db),
):
    """Add multiple style examples at once."""
    if len(examples) > 20:
        raise HTTPException(status_code=400, detail="Max 20 examples per request")

    profile = await get_active_profile(db)
    saved = []
    for req in examples:
        if req.category not in VALID_CATEGORIES:
            continue
        ex = StyleExample(
            profile_id=profile.id if profile else None,
            category=req.category,
            content=req.content,
            source_label=req.source_label,
        )
        db.add(ex)
        saved.append(ex.id)

    await db.commit()
    return {"saved": len(saved), "message": "Call /style/rebuild to update the profile."}


@router.get("/examples")
async def list_examples(
    category: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List stored style examples."""
    query = select(StyleExample).order_by(StyleExample.created_at.desc()).limit(limit)
    if category:
        query = query.where(StyleExample.category == category)
    result = await db.execute(query)
    examples = result.scalars().all()
    return [
        {
            "id": ex.id,
            "category": ex.category,
            "content_preview": ex.content[:150] + ("..." if len(ex.content) > 150 else ""),
            "source_label": ex.source_label,
            "created_at": str(ex.created_at),
        }
        for ex in examples
    ]


@router.delete("/examples/{example_id}")
async def delete_example(example_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a style example."""
    example = await db.get(StyleExample, example_id)
    if not example:
        raise HTTPException(status_code=404, detail="Example not found")
    await db.delete(example)
    await db.commit()
    return {"deleted": example_id}


@router.post("/rebuild")
async def rebuild_style_profile(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Re-analyze all style examples and rebuild the active profile. Runs in background."""
    background_tasks.add_task(rebuild_profile, db)
    return {"status": "started", "message": "Profile rebuild started. Check /style/profile in ~15 seconds."}


@router.post("/rebuild/sync")
async def rebuild_style_profile_sync(db: AsyncSession = Depends(get_db)):
    """Re-analyze all examples and rebuild profile synchronously (may be slow)."""
    profile = await rebuild_profile(db)
    return {
        "status": "complete",
        "name": profile.name,
        "example_count": profile.example_count,
        "tone": profile.tone,
        "formality": profile.formality,
        "full_attributes": profile.full_attributes,
    }


@router.post("/analyze-sample")
async def analyze_sample(req: AddExampleRequest):
    """Analyze a single writing sample to preview style extraction (does not save)."""
    attributes = await analyze_style_examples([req.content])
    injection = build_style_injection(attributes)
    return {
        "attributes": attributes,
        "injection_preview": injection,
    }


@router.get("/injection-preview")
async def preview_injection(channel: str = "#neural", db: AsyncSession = Depends(get_db)):
    """Preview the style injection that will be added to generation prompts."""
    from backend.services.style_profile_service import get_style_injection_for_generation
    injection = await get_style_injection_for_generation(db, channel)
    return {"channel": channel, "injection": injection or "(no active profile — using defaults)"}
