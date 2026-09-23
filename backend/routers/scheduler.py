"""Scheduler management API — view and trigger scheduled jobs."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/scheduler", tags=["scheduler"])

JOB_DESCRIPTIONS = {
    "discover_ai": "Discover AI content via web search",
    "fetch_rss": "Fetch all configured RSS feeds",
    "discover_research": "Discover research papers via arXiv + web",
    "discover_hackathons": "Discover hackathons via Devpost + MLH",
    "fetch_x": "Fetch X/Twitter content",
    "discover_opportunities": "Discover student opportunities",
}


@router.get("")
async def list_jobs():
    """List all scheduled jobs and their next run times."""
    from backend.services.scheduler_service import get_scheduler, DEFAULT_JOBS
    sched = get_scheduler()

    if not sched.running:
        return {"running": False, "jobs": []}

    apscheduler_jobs = {j.id: j for j in sched.get_jobs()}
    jobs_out = []

    for cfg in DEFAULT_JOBS:
        job = apscheduler_jobs.get(cfg["id"])
        jobs_out.append({
            "id": cfg["id"],
            "description": cfg["description"],
            "cron": cfg["cron"],
            "next_run": str(job.next_run_time) if job and job.next_run_time else None,
            "pending": job.pending if job else False,
        })

    return {"running": True, "jobs": jobs_out}


@router.post("/{job_id}/run")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job immediately."""
    from backend.services.scheduler_service import get_scheduler, DEFAULT_JOBS
    import asyncio

    valid_ids = {cfg["id"]: cfg["func"] for cfg in DEFAULT_JOBS}
    if job_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}. Valid: {list(valid_ids)}")

    sched = get_scheduler()
    if sched.running:
        sched.modify_job(job_id, next_run_time=None)
        sched.get_job(job_id).modify(next_run_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    else:
        # Run directly if scheduler not started
        asyncio.create_task(valid_ids[job_id]())

    logger.info("scheduler.manual_trigger", job_id=job_id)
    return {"status": "triggered", "job_id": job_id}


@router.post("/{job_id}/run-sync")
async def trigger_job_sync(job_id: str):
    """Run a scheduled job synchronously and wait for it to complete."""
    from backend.services.scheduler_service import DEFAULT_JOBS

    valid_ids = {cfg["id"]: cfg["func"] for cfg in DEFAULT_JOBS}
    if job_id not in valid_ids:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")

    logger.info("scheduler.sync_trigger", job_id=job_id)
    await valid_ids[job_id]()
    return {"status": "complete", "job_id": job_id}
