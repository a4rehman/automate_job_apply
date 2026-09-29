"""
Standalone runner for periodic automation cycles (cron / CLI / GitHub Actions).
Calls the identical AutomationPipeline service used by Streamlit UI.
"""
import asyncio
import argparse
import sys
from app.core.database import AsyncSessionLocal, init_db, ping_database
from app.models.job import RunStatus
from app.services.automation_pipeline import automation_pipeline
from app.core.logging_config import logger


async def main():
    parser = argparse.ArgumentParser(description="Run automated AI job discovery and application pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Force dry run mode (no live submissions).")
    parser.add_argument("--mode", type=str, default=None, choices=["SAFE_MODE", "ASSISTED_MODE", "AUTHORIZED_AUTO_MODE"], help="Automation execution mode.")
    parser.add_argument("--user-id", type=int, default=None, help="Target user ID to execute for.")
    args = parser.parse_args()

    logger.info("Initializing database...")
    await init_db()

    is_connected = await ping_database()
    if not is_connected:
        logger.error("Could not connect to database. Exiting.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        result = await automation_pipeline.run_cycle(
            db=db,
            user_id=args.user_id,
            dry_run=args.dry_run if args.dry_run else None,
            mode=args.mode,
        )
        logger.info(f"Pipeline Result: {result}")
        status = result.get("status")
        # Compare against the RunStatus vocabulary, not lowercase literals --
        # a stale string comparison here would exit 0 on a failed cycle.
        if status in (RunStatus.FAILED, RunStatus.PARTIAL_SUCCESS, RunStatus.INCOMPLETE):
            logger.error(f"Automation cycle did not complete successfully: {status}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
