from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job, JobMatch, JobStatus
from app.models.user import User, UserProfile
from app.models.resume import Skill, Resume
from app.models.notification import NotificationLevel
from app.services.matching_engine import matching_engine
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service
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
            select(Job).where(Job.status == JobStatus.NEW).order_by(Job.detected_date.desc()).limit(limit)
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
                
                # Determine status
                if score >= 90.0:
                    job.status = JobStatus.HIGH_MATCH
                elif score >= 75.0:
                    job.status = JobStatus.ANALYZED
                else:
                    job.status = JobStatus.LOW_MATCH

                # Create or update JobMatch
                job_match = JobMatch(
                    job_id=job.id,
                    user_id=user.id,
                    overall_score=score,
                    skills_score=match_result["skills_score"],
                    role_score=match_result["role_score"],
                    experience_score=match_result["experience_score"],
                    semantic_score=match_result["semantic_score"],
                    location_score=match_result["location_score"],
                    salary_score=match_result["salary_score"],
                    matching_skills=match_result["matching_skills"],
                    missing_skills=match_result["missing_skills"],
                    reasoning=match_result["reasoning"],
                    recommendation=match_result["recommendation"]
                )
                db.add(job_match)

                # If score >= 90%, trigger high priority notification
                if score >= 90.0:
                    top_skills = ", ".join(match_result["matching_skills"][:4])
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
