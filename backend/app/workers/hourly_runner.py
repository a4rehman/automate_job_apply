"""Hourly automation worker entry point.

Runs the full automation cycle independent of Streamlit or the API server.
Intended for: GitHub Actions scheduler / cron / manual `python -m app.workers.hourly_runner`.

Usage:
    python -m app.workers.hourly_runner            # dry run (safe default)
    python -m app.workers.hourly_runner --live     # attempt real submissions
"""
import argparse
import asyncio
import sys

from app.core.database import AsyncSessionLocal, init_db_with_migrations, ping_database
from app.core.config import settings
from app.core.logging_config import logger
from app.models.job import RunStatus
from app.services.automation_pipeline import automation_pipeline


async def run_migrations_only() -> int:
    """Apply pending schema migrations. Used by the GitHub Actions migrate step."""
    if not await ping_database():
        logger.error("Cannot reach the database; aborting migrations.")
        return 1
    await init_db_with_migrations()
    logger.info("Schema migrations complete.")
    return 0


async def main(live: bool = False) -> int:
    dry_run = not live
    logger.info(f"Hourly runner starting. dry_run={dry_run}, DRY_RUN env={settings.DRY_RUN}")

    # A live run is still refused unless the master switch is explicitly enabled.
    if not dry_run and not settings.AUTO_SUBMIT_ENABLED:
        logger.error(
            "--live requested but AUTO_SUBMIT_ENABLED is False. "
            "Refusing to run; set AUTO_SUBMIT_ENABLED=true explicitly to override."
        )
        return 1

    async with AsyncSessionLocal() as db:
        result = await automation_pipeline.run_cycle(db=db, dry_run=dry_run)

    status = result.get("status", "unknown")
    logger.info(f"Automation cycle finished with status: {status}")
    logger.info(f"Summary: {result}")

    if status == RunStatus.FAILED:
        return 1
    if status == RunStatus.SKIPPED:
        logger.info("Cycle skipped (another run in progress). Exiting 0.")
        return 0
    if status == RunStatus.PARTIAL_SUCCESS:
        # Some units of work succeeded and some failed. Surface this as a
        # failure so GitHub Actions flags it, but keep the partial data.
        logger.error("Cycle partially succeeded — review source/application health.")
        return 2
    if status == RunStatus.INCOMPLETE:
        # The cycle could not start at all. Exiting 0 here would report
        # success for a run that did no work, so it is a non-zero exit.
        logger.error(
            f"Cycle incomplete ({result.get('reason', 'unknown')}) — no work was done. "
            "Configure a user profile before the next scheduled run."
        )
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the job automation cycle.")
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Allow real submissions (default: dry run).",
    )
    parser.add_argument(
        "--migrate-only",
        action="store_true",
        default=False,
        help="Apply pending schema migrations and exit without running a cycle.",
    )
    args = parser.parse_args()
    if args.migrate_only:
        sys.exit(asyncio.run(run_migrations_only()))
    rc = asyncio.run(main(live=args.live))
    sys.exit(rc)