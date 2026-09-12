import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job, JobMatch, JobStatus
from app.models.application import Application, ApplicationAnswer, ApplicationStatus
from app.models.user import User, UserProfile
from app.models.resume import Resume, Skill
from app.ai.cover_letter import cover_letter_generator
from app.ai.client import ai_client
from app.ai.prompts import QA_GENERATOR_SYSTEM_PROMPT
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service
from app.models.notification import NotificationLevel
from app.core.logging_config import logger


class ApplicationService:
    """Orchestrates the full application preparation pipeline."""

    @staticmethod
    async def prepare_application(
        db: AsyncSession,
        user: User,
        job_id: int,
        resume_id: int | None = None,
        custom_instructions: str = "",
    ) -> Application:
        # Fetch job
        job_q = await db.execute(select(Job).where(Job.id == job_id))
        job = job_q.scalar_one_or_none()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Fetch profile
        prof_q = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = prof_q.scalar_one_or_none()
        if not profile:
            raise ValueError("User profile not found. Please complete your profile first.")

        # Fetch resume
        if resume_id:
            res_q = await db.execute(select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id))
        else:
            res_q = await db.execute(
                select(Resume).where(Resume.user_id == user.id, Resume.is_primary == True)
            )
        resume = res_q.scalar_one_or_none()
        resume_summary = resume.parsed_summary if resume else profile.bio or ""
        resume_text = resume.raw_text if resume else ""

        # Fetch user skills
        skills_q = await db.execute(select(Skill).where(Skill.user_id == user.id))
        user_skills = [s.name for s in skills_q.scalars().all()]

        # Generate cover letter
        cover_letter = await cover_letter_generator.generate(
            candidate_name=profile.full_name or "Candidate",
            candidate_summary=resume_summary,
            candidate_skills=user_skills,
            job_title=job.title,
            company=job.company,
            job_description=job.description,
            custom_instructions=custom_instructions,
        )

        # Get match details for context
        match_q = await db.execute(
            select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == user.id)
        )
        match = match_q.scalar_one_or_none()
        matching_skills = match.matching_skills if match else user_skills[:5]
        missing_skills = match.missing_skills if match else []

        custom_pitch = (
            f"I bring strong experience in {', '.join(matching_skills[:4])} "
            f"which directly aligns with your requirements for {job.title} at {job.company}."
        )

        # Create or update application record
        existing_q = await db.execute(
            select(Application).where(Application.job_id == job.id, Application.user_id == user.id)
        )
        application = existing_q.scalar_one_or_none()

        if application:
            application.status = ApplicationStatus.PREPARING
            application.cover_letter_text = cover_letter
            application.custom_pitch = custom_pitch
            application.resume_id = resume.id if resume else None
            application.tailored_resume_bullets = [
                {"skill": s, "status": "matched"} for s in matching_skills
            ] + [
                {"skill": s, "status": "gap"} for s in missing_skills
            ]
        else:
            application = Application(
                user_id=user.id,
                job_id=job.id,
                resume_id=resume.id if resume else None,
                status=ApplicationStatus.PREPARING,
                cover_letter_text=cover_letter,
                custom_pitch=custom_pitch,
                tailored_resume_bullets=[
                    {"skill": s, "status": "matched"} for s in matching_skills
                ] + [
                    {"skill": s, "status": "gap"} for s in missing_skills
                ],
                requires_user_approval=True,
                portal_submission_type="MANUAL_APPROVED",
            )
            db.add(application)

        await db.flush()

        # Update status to PENDING_APPROVAL
        application.status = ApplicationStatus.PENDING_APPROVAL
        job.status = JobStatus.PENDING_APPROVAL

        await db.commit()
        await db.refresh(application)

        await audit_service.log_event(
            db=db,
            event_type="APPLICATION_PREPARED",
            user_id=user.id,
            entity_type="APPLICATION",
            entity_id=application.id,
            details={"job_id": job.id, "job_title": job.title, "company": job.company},
        )

        await notification_service.create_notification(
            db=db,
            user_id=user.id,
            title=f"📋 Application Ready: {job.title}",
            message=f"Your application for {job.title} at {job.company} is ready for review.",
            level=NotificationLevel.ACTION_REQUIRED,
            link=f"/applications?id={application.id}",
        )

        return application

    @staticmethod
    async def generate_application_answer(
        db: AsyncSession,
        application_id: int,
        user: User,
        question_text: str,
        custom_context: str = "",
    ) -> ApplicationAnswer:
        """Generate a contextual answer for an application question."""
        app_q = await db.execute(
            select(Application).where(Application.id == application_id, Application.user_id == user.id)
        )
        application = app_q.scalar_one_or_none()
        if not application:
            raise ValueError("Application not found")

        job_q = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_q.scalar_one_or_none()

        prof_q = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
        profile = prof_q.scalar_one_or_none()

        res_q = await db.execute(
            select(Resume).where(Resume.user_id == user.id, Resume.is_primary == True)
        )
        resume = res_q.scalar_one_or_none()

        skills_q = await db.execute(select(Skill).where(Skill.user_id == user.id))
        user_skills = [s.name for s in skills_q.scalars().all()]

        user_prompt = (
            f"Application Question: {question_text}\n\n"
            f"Candidate: {profile.full_name if profile else 'Candidate'}\n"
            f"Current Title: {profile.current_title if profile else 'Engineer'}\n"
            f"Skills: {', '.join(user_skills[:10])}\n"
            f"Resume Summary: {resume.parsed_summary[:1500] if resume else (profile.bio if profile else '')}\n\n"
            f"Company: {job.company if job else 'Target Company'}\n"
            f"Role: {job.title if job else 'Target Role'}\n"
            f"Job Description: {job.description[:2000] if job else ''}\n"
        )
        if custom_context:
            user_prompt += f"\nAdditional context: {custom_context}"

        raw = await ai_client.generate_chat_completion(
            system_prompt=QA_GENERATOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            response_format_json=True,
        )

        try:
            data = json.loads(raw)
            answer = data.get("answer", raw)
        except Exception:
            answer = raw

        qa = ApplicationAnswer(
            application_id=application.id,
            question_text=question_text,
            generated_answer=answer,
            category="MOTIVATION" if "why" in question_text.lower() else "GENERAL",
        )
        db.add(qa)
        await db.commit()
        await db.refresh(qa)
        return qa

    @staticmethod
    async def approve_application(
        db: AsyncSession,
        application_id: int,
        user: User,
        edited_cover_letter: str | None = None,
        notes: str | None = None,
    ) -> Application:
        app_q = await db.execute(
            select(Application).where(Application.id == application_id, Application.user_id == user.id)
        )
        application = app_q.scalar_one_or_none()
        if not application:
            raise ValueError("Application not found")

        from datetime import datetime, timezone

        application.is_user_approved = True
        application.approved_at = datetime.now(timezone.utc)
        application.status = ApplicationStatus.APPLIED
        application.applied_at = datetime.now(timezone.utc)
        if edited_cover_letter:
            application.cover_letter_text = edited_cover_letter
        if notes:
            application.notes = notes

        # Update job status
        job_q = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_q.scalar_one_or_none()
        if job:
            job.status = JobStatus.APPLIED

        await db.commit()
        await db.refresh(application)

        await audit_service.log_event(
            db=db,
            event_type="APPLICATION_APPROVED",
            user_id=user.id,
            entity_type="APPLICATION",
            entity_id=application.id,
        )
        return application


application_service = ApplicationService()
