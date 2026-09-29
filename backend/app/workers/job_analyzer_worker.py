from typing import List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job, JobMatch, JobStatus
from app.models.user import User, UserProfile
from app.models.resume import Skill, Resume
from app.models.notification import NotificationLevel
from app.services.matching_engine import matching_engine
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service
from app.core.config import settings
from app.core.logging_config import logger

class JobAnalyzerWorker:
    @staticmethod
    async def analyze_pending_jobs(db: AsyncSession, limit: int = 20) -> int:
        """Fetch unanalyzed jobs and execute AI match analysis against the primary user profile."""
        # Find active user & profile
        user_res = await db.execute(select(User).where(User.is_active == True).limit(1))
        user = user_res.scalar_one_or_none()
        if not user:
            logger.info("No active user profile to match jobs against.")
            return 0

        prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = prof_res.scalar_one_or_none()
        if not profile:
            return 0

        skills_res = await db.execute(select(Skill).where(Skill.user_id == user.id))
        user_skills = [s.name for s in skills_res.scalars().all()]

        res_query = await db.execute(select(Resume).where(Resume.user_id == user.id, Resume.is_primary == True))
        primary_resume = res_query.scalar_one_or_none()
        resume_summary = primary_resume.parsed_summary if primary_resume else profile.bio

        # Fetch jobs with NEW status
        jobs_res = await db.execute(
            select(Job).where(Job.status == JobStatus.NEW).order_by(Job.discovered_at.desc()).limit(limit)
        )
        new_jobs = jobs_res.scalars().all()
        analyzed_count = 0

        for job in new_jobs:
            try:
                match_result = await matching_engine.match_job(
                    job=job,
                    profile=profile,
                    user_skills=user_skills,
                    resume_summary=resume_summary
                )

                score = match_result["overall_score"]
                job.match_score = score

                # Determine status based on decision and score
                decision_cat = match_result.get("decision", "HUMAN_REVIEW")
                if decision_cat == "HIGH_MATCH" or score >= (settings.HIGH_MATCH_THRESHOLD * 100):
                    job.status = JobStatus.HIGH_MATCH
                elif decision_cat == "HUMAN_REVIEW" or score >= (settings.REVIEW_THRESHOLD * 100):
                    job.status = JobStatus.ANALYZED
                else:
                    job.status = JobStatus.LOW_MATCH

                # Create or update JobMatch (one row per job+user, enforced by
                # a unique constraint) so re-analysis never duplicates rows.
                match_values = dict(
                    overall_score=score,
                    skills_score=match_result.get("skills_score", 0.0),
                    role_score=match_result.get("role_score", 0.0),
                    experience_score=match_result.get("experience_score", 0.0),
                    seniority_score=match_result.get("seniority_score", 0.0),
                    semantic_score=match_result.get("semantic_score", 0.0),
                    location_score=match_result.get("location_score", 0.0),
                    salary_score=match_result.get("salary_score", 0.0),
                    # Never assume confidence we did not measure.
                    confidence=match_result.get("confidence", 0.0),
                    matching_skills=match_result.get("matching_skills", []),
                    missing_skills=match_result.get("missing_skills", []),
                    concerns=match_result.get("concerns", []),
                    application_method=match_result.get("application_method", "unknown"),
                    decision=decision_cat,
                    requires_human_review=match_result.get("requires_human_review", True),
                    reasoning=match_result.get("reasoning", ""),
                    match_reasons=match_result.get("match_reasons", []),
                    recommendation=match_result.get("recommendation", "RECOMMENDED"),
                    analyzed_at=datetime.now(timezone.utc),
                )

                existing_match = await db.execute(
                    select(JobMatch).where(
                        JobMatch.job_id == job.id, JobMatch.user_id == user.id
                    )
                )
                job_match = existing_match.scalar_one_or_none()
                if job_match is None:
                    job_match = JobMatch(job_id=job.id, user_id=user.id, **match_values)
                    db.add(job_match)
                else:
                    for key, val in match_values.items():
                        setattr(job_match, key, val)

                # If high match, trigger high priority notification
                if job.status == JobStatus.HIGH_MATCH:
                    top_skills = ", ".join(match_result.get("matching_skills", [])[:4])
                    await notification_service.create_notification(
                        db=db,
                        user_id=user.id,
                        title=f"🔥 High Match ({score}%): {job.title}",
                        message=f"New High Match Job Found!\nCompany: {job.company}\nRole: {job.title}\nMatch: {score}%\nKey Skills: {top_skills}",
                        level=NotificationLevel.HIGH_MATCH,
                        link=f"/jobs?id={job.id}"
                    )

                analyzed_count += 1
            except Exception as e:
                logger.error(f"Failed to analyze job {job.id} ({job.title}): {e}")
                job.status = JobStatus.FAILED

        await db.commit()
        logger.info(f"Analyzed {analyzed_count} pending jobs.")
        return analyzed_count

job_analyzer_worker = JobAnalyzerWorker()

