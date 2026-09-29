import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.logging_config import logger
from app.services.automation_pipeline import automation_pipeline

scheduler = AsyncIOScheduler()


async def scheduled_job_cycle():
    """Run full automation cycle."""
    logger.info("⏰ Scheduled job cycle starting...")
    try:
        async with AsyncSessionLocal() as db:
            result = await automation_pipeline.run_cycle(db=db)
            logger.info(f"Cycle result: {result}")
    except Exception as e:
        logger.error(f"Scheduled job cycle failed: {e}")


def start_scheduler(interval_minutes: int | None = None):
    """Start the background APScheduler with the configured interval.
    
    Only starts once - prevents duplicate scheduler creation."""
    interval = interval_minutes or settings.DEFAULT_MONITOR_INTERVAL_MINUTES
    if scheduler.running:
        logger.info("Scheduler already running, skipping start.")
        return

    scheduler.add_job(
        scheduled_job_cycle,
        trigger=IntervalTrigger(minutes=interval),
        id="automation_cycle",
        name="Automation Cycle",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
        coalesce=True,
    )
    scheduler.start()
    logger.info(f"✅ Background scheduler started (interval: {interval} minutes)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Background scheduler stopped")


async def run_automation_cycle(db: AsyncSession, dry_run: bool = False) -> dict:
    """Run a single automation cycle (for GitHub Actions and manual triggers)."""
    return await automation_pipeline.run_cycle(db=db, dry_run=dry_run)