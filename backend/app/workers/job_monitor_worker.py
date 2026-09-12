import asyncio
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.core.logging_config import logger
from app.models.job import Job, JobSourceConfig, JobStatus
from app.job_sources import get_all_active_sources
from app.job_sources.base import NormalizedJob
from app.services.audit_service import audit_service

class JobMonitorWorker:
    @staticmethod
    async def poll_all_sources(db: AsyncSession) -> Dict[str, Any]:
        """Poll all enabled job sources and ingest new non-duplicate postings."""
        sources = get_all_active_sources()
        total_discovered = 0
        total_duplicates = 0
        newly_inserted_jobs: List[Job] = []

        logger.info(f"Starting job monitor polling across {len(sources)} active sources...")

        for source in sources:
            try:
                raw_jobs = await source.fetch_jobs(limit=25)
                for raw_job in raw_jobs:
                    normalized = await source.normalize_job(raw_job)
                    if not normalized:
                        continue

                    total_discovered += 1
                    
                    # Duplicate Detection: SHA256 hash or exact URL or (Title + Company)
                    query = select(Job).where(
                        or_(
                            Job.description_hash == normalized.description_hash,
                            (Job.job_url != "") & (Job.job_url == normalized.job_url),
                            (Job.title.ilike(normalized.title.strip())) & (Job.company.ilike(normalized.company.strip()))
                        )
                    )
                    existing = await db.execute(query)
                    if existing.scalar_one_or_none():
                        total_duplicates += 1
                        continue

                    # Insert new Job
                    new_job = Job(
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
                        posted_date=normalized.posted_date,
                        status=JobStatus.NEW,
                        match_score=0.0
                    )
                    db.add(new_job)
                    newly_inserted_jobs.append(new_job)

                await db.commit()
            except Exception as e:
                logger.error(f"Error polling source {source.name}: {e}")
                await db.rollback()

        logger.info(
            f"Job monitor poll complete: Discovered {total_discovered}, "
            f"Added {len(newly_inserted_jobs)}, Duplicates skipped {total_duplicates}"
        )

        return {
            "total_discovered": total_discovered,
            "new_jobs_added": len(newly_inserted_jobs),
            "duplicates_skipped": total_duplicates,
            "job_ids": [j.id for j in newly_inserted_jobs]
        }

job_monitor_worker = JobMonitorWorker()
