import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.core.errors import log_classified_error
from app.core.logging_config import logger
from app.models.job import Job, JobSourceConfig, JobStatus, JobSourceHealth, SourceHealth
from app.job_sources import get_all_active_sources
from app.job_sources.base import NormalizedJob
from app.services.audit_service import audit_service


class JobMonitorWorker:
    @staticmethod
    async def poll_all_sources(db: AsyncSession) -> Dict[str, Any]:
        """Poll all enabled job sources and ingest new non-duplicate postings."""
        # Ensure source config rows exist so per-source enable/disable gating works
        from app.services.source_config_service import sync_source_configs
        await sync_source_configs(db)

        sources = get_all_active_sources()
        total_discovered = 0
        total_duplicates = 0
        # Plain ints only. Holding ORM Job objects and reading .id after a
        # commit/rollback forces an implicit lazy load, which raises
        # MissingGreenlet in async code once a rollback has expired the session.
        inserted_ids: List[int] = []

        # Load source configs for linking & health tracking
        cfg_res = await db.execute(select(JobSourceConfig))
        configs = cfg_res.scalars().all()
        cfg_map = {c.name: c for c in configs}
        # Snapshot the values we gate on into plain Python data. A rollback for
        # one source expires every object in the session, so a later iteration
        # must never read an ORM attribute off a previously-loaded instance.
        source_meta = {
            c.name: {"id": c.id, "is_enabled": c.is_enabled} for c in configs
        }

        logger.info(f"Starting job monitor polling across {len(sources)} active sources...")

        for source in sources:
            meta = source_meta.get(source.name)
            if meta and not meta["is_enabled"]:
                logger.info(f"Skipping disabled source {source.name}")
                continue

            pending: List[Job] = []
            source_ids: List[int] = []
            try:
                raw_jobs = await source.fetch_jobs(limit=25)
                for raw_job in raw_jobs:
                    normalized = await source.normalize_job(raw_job)
                    if not normalized:
                        continue

                    total_discovered += 1

                    # Duplicate Detection: SHA256 hash, normalized/exact URL, or (Title + Company)
                    query = select(Job).where(
                        or_(
                            Job.description_hash == normalized.description_hash,
                            (Job.normalized_url != "") & (Job.normalized_url == normalized.normalized_url),
                            (Job.title.ilike(normalized.title.strip())) & (Job.company.ilike(normalized.company.strip()))
                        )
                    )
                    existing = await db.execute(query)
                    if existing.scalar_one_or_none():
                        total_duplicates += 1
                        continue

                    # Insert new Job
                    new_job = Job(
                        source_id=meta["id"] if meta else None,
                        source_name=normalized.source_name,
                        external_job_id=normalized.external_job_id or "",
                        title=normalized.title,
                        company=normalized.company,
                        location=normalized.location,
                        remote_type=normalized.remote_type,
                        employment_type=normalized.employment_type,
                        salary_min=normalized.salary_min,
                        salary_max=normalized.salary_max,
                        currency=normalized.currency,
                        description=normalized.description,
                        description_hash=normalized.description_hash,
                        requirements=normalized.requirements,
                        preferred_skills=normalized.preferred_skills,
                        skills=normalized.skills,
                        experience_years_required=normalized.experience_years_required,
                        job_url=normalized.job_url,
                        normalized_url=normalized.normalized_url,
                        posted_date=normalized.posted_date or None,
                        status=JobStatus.NEW,
                        match_score=0.0
                    )
                    db.add(new_job)
                    pending.append(new_job)

                # Flush assigns primary keys without ending the transaction, so
                # the IDs can be read while the objects are still loaded.
                if pending:
                    await db.flush()
                    source_ids = [p.id for p in pending]

                # Mark source healthy on success
                await JobMonitorWorker._set_source_config_health(
                    db, source.name, healthy=True
                )

                await db.commit()
                # Only count the IDs once this source's work is durably committed.
                inserted_ids.extend(source_ids)

                await JobMonitorWorker._record_source_health(db, source.name, success=True, error="")
            except Exception as e:
                etype = log_classified_error(f"monitor_poll:{source.name}", e)
                await db.rollback()
                # The pending Job objects for this source were expunged by the
                # rollback, so source_ids is intentionally dropped.
                await JobMonitorWorker._set_source_config_health(
                    db, source.name, healthy=False
                )
                await JobMonitorWorker._record_source_health(
                    db, source.name, success=False, error=f"[{etype}] {e}"
                )
                await db.commit()

        logger.info(
            f"Job monitor poll complete: Discovered {total_discovered}, "
            f"Added {len(inserted_ids)}, Duplicates skipped {total_duplicates}"
        )

        return {
            "total_discovered": total_discovered,
            "new_jobs_added": len(inserted_ids),
            "duplicates_skipped": total_duplicates,
            "job_ids": inserted_ids,
        }

    @staticmethod
    async def _set_source_config_health(db: AsyncSession, source_name: str, healthy: bool):
        """Update the JobSourceConfig health columns.

        Always re-reads the row instead of reusing a cached instance: a rollback
        expires every object in the session, and reading a column off an expired
        instance attempts a lazy load that is not permitted in an async session.
        """
        res = await db.execute(
            select(JobSourceConfig).where(JobSourceConfig.name == source_name)
        )
        cfg = res.scalar_one_or_none()
        if not cfg:
            return
        if healthy:
            cfg.health_status = JobSourceHealth.HEALTHY
            cfg.consecutive_failures = 0
        else:
            cfg.consecutive_failures = (cfg.consecutive_failures or 0) + 1
            cfg.health_status = (
                JobSourceHealth.DEGRADED
                if cfg.consecutive_failures < 3
                else JobSourceHealth.FAILED
            )
        cfg.last_polled_at = datetime.now(timezone.utc)

    @staticmethod
    async def _record_source_health(db: AsyncSession, source_name: str, success: bool, error: str = ""):
        """Update/insert source health telemetry row."""
        res = await db.execute(select(SourceHealth).where(SourceHealth.source_name == source_name))
        health = res.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not health:
            health = SourceHealth(source_name=source_name, last_check_at=now)
            db.add(health)

        health.last_check_at = now
        health.total_fetches = (health.total_fetches or 0) + 1
        if success:
            health.consecutive_failures = 0
            health.status = JobSourceHealth.HEALTHY
        else:
            health.total_failures = (health.total_failures or 0) + 1
            health.consecutive_failures = (health.consecutive_failures or 0) + 1
            health.status = JobSourceHealth.FAILED
            health.last_error = (error or "")[:1000]


job_monitor_worker = JobMonitorWorker()