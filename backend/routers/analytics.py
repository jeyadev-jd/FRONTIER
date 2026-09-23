"""Analytics API — funnel stats, breakdowns, activity history."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.services.analytics_service import (
    get_funnel_stats, get_category_breakdown,
    get_channel_breakdown, get_daily_activity, get_top_content
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def summary(days: int = 7, db: AsyncSession = Depends(get_db)):
    funnel = await get_funnel_stats(db, days=days)
    categories = await get_category_breakdown(db, days=days)
    channels = await get_channel_breakdown(db, days=days)
    return {
        "funnel": funnel,
        "by_category": categories,
        "by_channel": channels,
    }


@router.get("/activity")
async def activity(days: int = 14, db: AsyncSession = Depends(get_db)):
    return await get_daily_activity(db, days=days)


@router.get("/top-content")
async def top_content(limit: int = 10, db: AsyncSession = Depends(get_db)):
    return await get_top_content(db, limit=limit)
