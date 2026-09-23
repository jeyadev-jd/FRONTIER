"""Auto-publish rules API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from backend.database.db import get_db
from backend.services.autopublish_service import (
    AutoPublishRule, get_rules, seed_default_rules,
    apply_auto_publish_rules, BLOCKED_CHANNELS, MAX_AUTO_PUBLISH_PER_CYCLE,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/autopublish", tags=["autopublish"])


class RuleUpdate(BaseModel):
    is_enabled: bool | None = None
    min_score: float | None = None
    channel: str | None = None
    category: str | None = None


@router.get("/rules")
async def list_rules(db: AsyncSession = Depends(get_db)):
    await seed_default_rules(db)
    rules = await get_rules(db)
    return [
        {
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "channel": r.channel,
            "min_score": r.min_score,
            "is_enabled": r.is_enabled,
        }
        for r in rules
    ]


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: int, req: RuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AutoPublishRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if req.is_enabled is not None:
        # Safety: block enabling for protected channels
        if req.is_enabled and rule.channel in BLOCKED_CHANNELS:
            raise HTTPException(status_code=400, detail=f"{rule.channel} cannot be auto-published")
        rule.is_enabled = req.is_enabled

    if req.min_score is not None:
        if not (0.5 <= req.min_score <= 1.0):
            raise HTTPException(status_code=400, detail="min_score must be 0.5–1.0")
        rule.min_score = req.min_score

    if req.channel is not None:
        if req.channel in BLOCKED_CHANNELS:
            raise HTTPException(status_code=400, detail=f"{req.channel} cannot be auto-published")
        rule.channel = req.channel or None

    if req.category is not None:
        rule.category = req.category or None

    await db.commit()
    return {"id": rule_id, "name": rule.name, "is_enabled": rule.is_enabled, "min_score": rule.min_score}


@router.post("/run")
async def run_autopublish(db: AsyncSession = Depends(get_db)):
    """Apply auto-publish rules to pending queue now."""
    count = await apply_auto_publish_rules(db)
    return {"auto_published": count, "max_per_cycle": MAX_AUTO_PUBLISH_PER_CYCLE}


@router.get("/config")
async def get_config():
    return {
        "blocked_channels": list(BLOCKED_CHANNELS),
        "max_per_cycle": MAX_AUTO_PUBLISH_PER_CYCLE,
        "note": "Enable rules carefully. Auto-published posts bypass human review.",
    }
