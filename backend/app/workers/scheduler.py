import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.logging_config import logger
from app.workers.job_monitor_worker import job_monitor_worker
from app.workers.job_analyzer_worker import job_analyzer_worker

scheduler = AsyncIOScheduler()


async def scheduled_job_cycle():
    """Run full discovery + analysis cycle."""
    logger.info("⏰ Scheduled job cycle starting...")
    try:
        async with AsyncSessionLocal() as db:
            result = await job_monitor_worker.poll_all_sources(db=db)
            logger.info(f"Monitor result: {result['new_jobs_added']} new jobs, {result['duplicates_skipped']} dups")
            analyzed = await job_analyzer_worker.analyze_pending_jobs(db=db)
            logger.info(f"Analyzer result: {analyzed} jobs analyzed")
    except Exception as e:
        logger.error(f"Scheduled job cycle failed: {e}")


def start_scheduler(interval_minutes: int | None = None):
    """Start the background APScheduler with the configured interval."""
    interval = interval_minutes or settings.DEFAULT_MONITOR_INTERVAL_MINUTES
    if scheduler.running:
        logger.info("Scheduler already running, skipping start.")
        return

    scheduler.add_job(
        scheduled_job_cycle,
        trigger=IntervalTrigger(minutes=interval),
        id="job_monitor_cycle",
        name="Job Monitor + Analyzer Cycle",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"✅ Background scheduler started (interval: {interval} minutes)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Background scheduler stopped")
