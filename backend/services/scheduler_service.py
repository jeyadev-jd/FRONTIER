"""
FRONTIER Scheduler — APScheduler with named jobs.
Runs inside the same process as the FastAPI backend.

Default schedule:
  08:00  discover AI content
  10:00  fetch RSS feeds (AI + BUILD)
  12:00  discover research / arXiv
  14:00  fetch RSS feeds (RESEARCH + OPPORTUNITY)
  16:00  discover hackathons
  18:00  fetch X content
  20:00  discover opportunities
"""
import asyncio
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.add_listener(_on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
    return _scheduler


def _on_job_event(event):
    if event.exception:
        logger.error("scheduler.job_failed", job_id=event.job_id, error=str(event.exception))
    else:
        logger.info("scheduler.job_complete", job_id=event.job_id)


# ──────────────────────────────────────────────
# Job functions
# ──────────────────────────────────────────────

async def job_discover_ai():
    logger.info("job.discover_ai.start")
    from backend.database.db import AsyncSessionLocal
    from backend.services.discovery_service import discover_by_category
    async with AsyncSessionLocal() as db:
        items = await discover_by_category(db, "AI", max_items=10)
    logger.info("job.discover_ai.done", saved=len(items))


async def job_discover_research():
    logger.info("job.discover_research.start")
    from backend.database.db import AsyncSessionLocal
    from backend.services.discovery_service import discover_by_category, discover_ai_papers
    async with AsyncSessionLocal() as db:
        papers = await discover_ai_papers(db, max_items=8)
        web = await discover_by_category(db, "RESEARCH", max_items=5)
    logger.info("job.discover_research.done", papers=len(papers), web=len(web))


async def job_discover_hackathons():
    logger.info("job.discover_hackathons.start")
    from backend.database.db import AsyncSessionLocal
    from backend.services.hackathon_service import discover_hackathons
    from backend.services.discovery_service import _process_result
    from backend.config import get_settings

    settings = get_settings()
    hackathons = await discover_hackathons(max_items=20)

    saved = 0
    async with AsyncSessionLocal() as db:
        for h in hackathons:
            try:
                ci = await _process_result(db, h, "HACKATHON", settings)
                if ci:
                    saved += 1
            except Exception as e:
                logger.warning("job.hackathon.item_error", error=str(e)[:80])
            await asyncio.sleep(0.3)

    logger.info("job.discover_hackathons.done", saved=saved)


async def job_fetch_rss():
    logger.info("job.fetch_rss.start")
    from backend.database.db import AsyncSessionLocal
    from backend.services.rss_service import fetch_all_feeds
    from backend.services.discovery_service import _process_result
    from backend.config import get_settings

    settings = get_settings()
    items = await fetch_all_feeds(days_back=2)

    saved = 0
    async with AsyncSessionLocal() as db:
        for item in items:
            try:
                ci = await _process_result(db, item, item.get("category", "GENERAL"), settings)
                if ci:
                    saved += 1
            except Exception as e:
                logger.warning("job.rss.item_error", error=str(e)[:80])
            await asyncio.sleep(0.2)

    logger.info("job.fetch_rss.done", saved=saved)


async def job_fetch_x():
    logger.info("job.fetch_x.start")
    from backend.config import get_settings
    settings = get_settings()
    if not settings.x_bearer_token:
        logger.info("job.fetch_x.skipped", reason="no bearer token")
        return

    from backend.database.db import AsyncSessionLocal
    from backend.services.x_service import discover_x_by_category
    from backend.services.discovery_service import _process_result

    saved = 0
    async with AsyncSessionLocal() as db:
        for category in ["AI", "BUILD", "RESEARCH", "HACKATHON"]:
            tweets = await discover_x_by_category(category, max_results=8)
            for t in tweets:
                try:
                    ci = await _process_result(db, t, category, settings)
                    if ci:
                        saved += 1
                except Exception as e:
                    logger.warning("job.x.item_error", error=str(e)[:80])
            await asyncio.sleep(2)

    logger.info("job.fetch_x.done", saved=saved)


async def job_discover_opportunities():
    logger.info("job.discover_opportunities.start")
    from backend.database.db import AsyncSessionLocal
    from backend.services.discovery_service import discover_by_category
    async with AsyncSessionLocal() as db:
        items = await discover_by_category(db, "OPPORTUNITY", max_items=8)
    logger.info("job.discover_opportunities.done", saved=len(items))


async def job_queue_cycle():
    """Auto-draft high-relevance items and expire stale content."""
    from backend.services.queue_service import run_queue_cycle
    await run_queue_cycle()


# ──────────────────────────────────────────────
# Schedule configuration
# ──────────────────────────────────────────────

DEFAULT_JOBS = [
    {
        "id": "discover_ai",
        "func": job_discover_ai,
        "cron": "0 8 * * *",
        "description": "Discover AI content via web search",
    },
    {
        "id": "fetch_rss",
        "func": job_fetch_rss,
        "cron": "0 10,14 * * *",
        "description": "Fetch configured RSS feeds",
    },
    {
        "id": "discover_research",
        "func": job_discover_research,
        "cron": "0 12 * * *",
        "description": "Discover research papers via arXiv + web",
    },
    {
        "id": "discover_hackathons",
        "func": job_discover_hackathons,
        "cron": "0 16 * * *",
        "description": "Discover hackathons via Devpost + MLH",
    },
    {
        "id": "fetch_x",
        "func": job_fetch_x,
        "cron": "0 18 * * *",
        "description": "Fetch X/Twitter content (requires X_BEARER_TOKEN)",
    },
    {
        "id": "discover_opportunities",
        "func": job_discover_opportunities,
        "cron": "0 20 * * *",
        "description": "Discover student opportunities and internships",
    },
    {
        "id": "queue_cycle",
        "func": job_queue_cycle,
        "cron": "0 9,13,17,21 * * *",
        "description": "Auto-draft high-relevance items and expire stale content",
    },
]


def setup_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler with all default jobs."""
    sched = get_scheduler()

    for job_cfg in DEFAULT_JOBS:
        hour, minute = _parse_cron_time(job_cfg["cron"])
        sched.add_job(
            job_cfg["func"],
            trigger=CronTrigger(hour=hour, minute=minute, timezone="UTC"),
            id=job_cfg["id"],
            name=job_cfg["description"],
            replace_existing=True,
            misfire_grace_time=3600,
        )

    logger.info("scheduler.configured", jobs=len(DEFAULT_JOBS))
    return sched


def _parse_cron_time(cron: str) -> tuple[str, str]:
    """Extract hour and minute from 'minute hour * * *' cron expression."""
    parts = cron.split()
    return parts[1], parts[0]


def start_scheduler() -> AsyncIOScheduler:
    sched = setup_scheduler()
    sched.start()
    logger.info("scheduler.started")
    return sched


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")
