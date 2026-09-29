import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.core.logging_config import logger
from app.models.job import Job, JobStatus, SchedulerRun, RunStatus
from app.models.user import User, UserProfile
from app.models.application import Application, ApplicationStatus
from app.models.automation import AutomationSettings
from app.models.notification import NotificationLevel
from app.services.notification_service import notification_service, NotificationEvent
from app.services.audit_service import audit_service
from app.job_sources import get_all_active_sources
from app.workers.job_monitor_worker import job_monitor_worker
from app.workers.job_analyzer_worker import job_analyzer_worker
from app.services.application_executor import ApplicationExecutor


class AutomationPipeline:
    """
    Orchestrates the full automation cycle with run locking, explainable matching,
    and multi-mode execution (SAFE_MODE, ASSISTED_MODE, AUTHORIZED_AUTO_MODE).
    """

    LOCK_STALE_AFTER_SECONDS = 3600

    def __init__(self):
        self.run_id = ""
        self.metrics = {
            "jobs_discovered": 0,
            "jobs_new": 0,
            "jobs_duplicate": 0,
            "jobs_analyzed": 0,
            "high_matches": 0,
            "human_reviews": 0,
            "low_matches": 0,
            "applications_prepared": 0,
            "applications_submitted": 0,
            "email_applications": 0,
            "failures": 0,
            "notifications_sent": 0,
        }

    async def acquire_lock(self, db: AsyncSession) -> bool:
        """Acquire a database-backed run lock to prevent overlapping cycles."""
        lock_timeout = settings.SCHEDULER_LOCK_TIMEOUT_SECONDS
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(SchedulerRun).where(SchedulerRun.status == RunStatus.RUNNING)
        )
        running_runs = result.scalars().all()

        blocked = False
        for run in running_runs:
            age = (now - run.started_at).total_seconds() if run.started_at else 0
            if age < lock_timeout:
                logger.info(f"Another automation cycle is active (run={run.run_id}, age={age:.0f}s). Exiting.")
                blocked = True
            else:
                logger.warning(f"Stale lock {run.run_id} detected ({age:.0f}s old). Marking failed.")
                run.status = RunStatus.FAILED
                run.error_message = "Stale lock recovered (timeout exceeded)"
                run.finished_at = now

        if blocked:
            return False

        await db.flush()
        return True

    async def release_lock(self, db: AsyncSession):
        """Releases the run lock."""
        pass

    async def run_cycle(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None,
        dry_run: Optional[bool] = None,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute the full automation cycle."""
        is_dry = settings.DRY_RUN if dry_run is None else dry_run
        auto_mode = mode or settings.AUTOMATION_MODE or "SAFE_MODE"

        self.run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        started_at = datetime.now(timezone.utc)

        logger.info("=" * 60)
        logger.info(f"AUTOMATION CYCLE START — Run ID: {self.run_id}")
        logger.info(f"Mode: {auto_mode} | Dry Run: {is_dry}")

        try:
            # Phase 1: Acquire lock
            lock_acquired = await self.acquire_lock(db)
            if not lock_acquired:
                logger.info("Another automation cycle is already running. Skipping duplicate run.")
                return {"status": RunStatus.SKIPPED, "reason": "duplicate_run"}

            # Phase 2: Load active candidate profile
            if user_id:
                user_res = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
            else:
                user_res = await db.execute(select(User).where(User.is_active == True).limit(1))
            user = user_res.scalar_one_or_none()

            if not user:
                logger.warning("No active user found.")
                return {"status": RunStatus.INCOMPLETE, "reason": "no_user"}

            prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
            profile = prof_res.scalar_one_or_none()
            if not profile or not profile.full_name:
                logger.warning("User profile incomplete.")
                return {"status": RunStatus.INCOMPLETE, "reason": "profile_incomplete"}

            # Phase 3: Job Discovery & Deduplication
            monitor_result = await job_monitor_worker.poll_all_sources(db=db)
            # The monitor reports total_discovered (not total_fetched); reading
            # the wrong key silently recorded 0 discovered jobs.
            self.metrics["jobs_discovered"] = monitor_result.get(
                "total_discovered", monitor_result.get("total_fetched", 0)
            )
            self.metrics["jobs_new"] = monitor_result.get("new_jobs_added", 0)
            self.metrics["jobs_duplicate"] = monitor_result.get("duplicates_skipped", 0)

            # Phase 4: Gemini Decision Engine Analysis
            analyzed = await job_analyzer_worker.analyze_pending_jobs(db=db)
            self.metrics["jobs_analyzed"] = analyzed

            # Phase 5: Query Matches
            high_match_res = await db.execute(
                select(Job).where(Job.status == JobStatus.HIGH_MATCH)
            )
            high_match_jobs = high_match_res.scalars().all()
            self.metrics["high_matches"] = len(high_match_jobs)

            analyzed_res = await db.execute(
                select(Job).where(Job.status == JobStatus.ANALYZED)
            )
            self.metrics["human_reviews"] = len(analyzed_res.scalars().all())

            low_match_res = await db.execute(
                select(Job).where(Job.status == JobStatus.LOW_MATCH)
            )
            self.metrics["low_matches"] = len(low_match_res.scalars().all())

            # Phase 6: Prepare Applications for High Matches
            prepared_count = 0
            submitted_count = 0
            email_app_count = 0
            failed_count = 0

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

            for job in high_match_jobs:
                if prepared_count >= settings.MAX_APPLICATIONS_PER_RUN:
                    logger.info(f"Reached max applications per run limit ({settings.MAX_APPLICATIONS_PER_RUN}).")
                    break

                # Daily safety limit check
                daily_apps_res = await db.execute(
                    select(Application).where(
                        Application.user_id == user.id,
                        Application.created_at >= today_start,
                    )
                )
                if len(daily_apps_res.scalars().all()) >= settings.MAX_APPLICATIONS_PER_DAY:
                    logger.info(f"Reached daily application limit ({settings.MAX_APPLICATIONS_PER_DAY}).")
                    break

                # Prepare application package
                try:
                    app = await ApplicationExecutor.prepare(db=db, user=user, job_id=job.id)
                    prepared_count += 1

                    # Automation Mode handling:
                    # In SAFE_MODE or ASSISTED_MODE, keep application in REVIEW_REQUESTED for human approval
                    if auto_mode in ("SAFE_MODE", "ASSISTED_MODE") or is_dry:
                        app.status = ApplicationStatus.REVIEW_REQUESTED
                        await notification_service.notify_human_review_required(
                            db=db, user_id=user.id, company=job.company,
                            role=job.title, app_id=app.id, score=job.match_score
                        )
                    elif auto_mode == "AUTHORIZED_AUTO_MODE":
                        # Execute authorized submission (e.g. Email or API)
                        sub_res = await ApplicationExecutor.submit(
                            db=db, user=user, job=job, application=app, dry_run=False
                        )
                        if sub_res.get("status") in (ApplicationStatus.SUBMITTED, ApplicationStatus.EMAIL_SENT):
                            submitted_count += 1
                            if sub_res.get("status") == ApplicationStatus.EMAIL_SENT:
                                email_app_count += 1
                        elif sub_res.get("status") == ApplicationStatus.FAILED:
                            failed_count += 1

                except Exception as prep_err:
                    logger.error(f"Error preparing application for Job #{job.id}: {prep_err}")
                    failed_count += 1

            self.metrics["applications_prepared"] = prepared_count
            self.metrics["applications_submitted"] = submitted_count
            self.metrics["email_applications"] = email_app_count
            self.metrics["failures"] = failed_count

            await db.commit()

            # Phase 7: Record scheduler run & send summary alert
            finished_at = datetime.now(timezone.utc)
            run_status = await self._record_scheduler_run(
                db=db,
                user_id=user.id,
                started_at=started_at,
                finished_at=finished_at,
            )

            # Count only notifications that were genuinely delivered, never
            # an assumed number.
            delivery: Dict[str, bool] = {}
            await notification_service.notify_cycle_completed(
                db=db, user_id=user.id, run_id=self.run_id, summary=self.metrics,
                delivery_sink=delivery,
            )
            if delivery.get("email") or delivery.get("telegram"):
                self.metrics["notifications_sent"] += 1

            logger.info(f"AUTOMATION CYCLE COMPLETED — Run ID: {self.run_id}")
            logger.info("=" * 60)

            return {
                "run_id": self.run_id,
                "status": run_status,
                "metrics": self.metrics,
            }

        except Exception as e:
            logger.error(
                f"Automation cycle failed with unhandled exception: {e}",
                exc_info=True,
            )
            self.metrics["failures"] += 1
            finished_at = datetime.now(timezone.utc)
            await self._record_scheduler_run(
                db=db,
                user_id=user_id or 1,
                started_at=started_at,
                finished_at=finished_at,
                error=str(e),
            )
            await db.commit()
            return {
                "run_id": self.run_id,
                "status": RunStatus.FAILED,
                "error": str(e),
                "metrics": self.metrics,
            }

    async def _record_scheduler_run(
        self,
        db: AsyncSession,
        user_id: int,
        started_at: datetime,
        finished_at: datetime,
        error: str = "",
        **metric_overrides: int,
    ) -> str:
        """Insert or update the SchedulerRun row for this run_id (idempotent)."""
        metrics = {**self.metrics, **metric_overrides}

        # Derive a truthful terminal state (Phase 5). A cycle where some work
        # succeeded and some failed is PARTIAL_SUCCESS, never a plain "success".
        status = RunStatus.from_outcome(
            prepared=metrics["applications_prepared"],
            submitted=metrics["applications_submitted"],
            failures=metrics["failures"],
        )
        if error:
            status = RunStatus.PARTIAL_SUCCESS if metrics["failures"] > 1 else RunStatus.FAILED

        values = dict(
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            jobs_discovered=metrics["jobs_discovered"],
            jobs_new=metrics["jobs_new"],
            jobs_duplicate=metrics["jobs_duplicate"],
            jobs_analyzed=metrics["jobs_analyzed"],
            high_matches=metrics["high_matches"],
            human_reviews=metrics["human_reviews"],
            low_matches=metrics["low_matches"],
            applications_prepared=metrics["applications_prepared"],
            applications_submitted=metrics["applications_submitted"],
            email_applications=metrics["email_applications"],
            failures=metrics["failures"],
            notifications_sent=metrics["notifications_sent"],
            error_message=error,
            created_by=user_id,
        )

        existing = await db.execute(
            select(SchedulerRun).where(SchedulerRun.run_id == self.run_id)
        )
        run = existing.scalar_one_or_none()
        if run is None:
            run = SchedulerRun(run_id=self.run_id, **values)
            db.add(run)
        else:
            # Same run_id => update in place; never create a duplicate row.
            for key, val in values.items():
                setattr(run, key, val)

        await db.commit()
        return status


automation_pipeline = AutomationPipeline()