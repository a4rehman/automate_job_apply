import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.application import (
    Application,
    ApplicationStatus,
    ApplicationPackage,
    ApplicationReview,
    ApplicationEvent,
    ExecutionAttempt,
)
from app.models.job import Job, JobStatus, JobSourceConfig, JobMatch
from app.models.user import User, UserProfile
from app.models.resume import Resume, Skill
from app.models.notification import NotificationLevel, OutboundEmail
from app.services.notification_service import notification_service, NotificationEvent
from app.services.audit_service import audit_service
from app.ai.decision_engine import gemini_provider, ApplicationEmailContent
from app.core.config import settings
from app.core.logging_config import logger


class EmailApplicationExecutor:
    """Executes applications directed via Email with grounded candidate facts and outbound tracking."""

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        user: User,
        job: Job,
        application: Application,
        profile: UserProfile,
        user_skills: List[str],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        is_dry_run = bool(dry_run or settings.DRY_RUN)

        # Idempotency guard runs FIRST -- before an ExecutionAttempt row is
        # created and before any AI call is spent. Checking later leaked an
        # IN_PROGRESS attempt on every retried cycle and re-billed extraction.
        if is_dry_run:
            dup = await db.execute(
                select(OutboundEmail)
                .where(
                    OutboundEmail.application_id == application.id,
                    OutboundEmail.status == "DRY_RUN_NOT_SENT",
                )
                .limit(1)
            )
            if dup.scalars().first() is not None:
                logger.info(
                    f"App #{application.id}: dry-run email already generated; "
                    "skipping duplicate without creating an attempt."
                )
                return {
                    "success": False,
                    "status": "DUPLICATE_SKIPPED",
                    "message": "Application already in a terminal state for this run: dry-run email already generated (duplicate skipped).",
                    "application_id": application.id,
                    "recipient": application.email_recipient or "",
                }

        attempt_number = (application.retry_count or 0) + 1
        idempotency_key = f"EMAIL-{user.id}-{job.id}-{attempt_number}"

        attempt = ExecutionAttempt(
            application_id=application.id,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key,
            submission_method="EMAIL",
            status="IN_PROGRESS",
            started_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        # 1. Identify or extract recipient email
        recipient_email = application.email_recipient
        if not recipient_email:
            extraction = await gemini_provider.extract_email_application(
                job_description=job.description,
                company=job.company,
                role=job.title,
            )
            if extraction.is_email_application and extraction.recipient_email:
                recipient_email = extraction.recipient_email
                application.email_recipient = recipient_email
                application.email_subject = extraction.email_subject or f"Application for {job.title} - {profile.full_name}"

        if not recipient_email:
            logger.warning(f"Email application requested for Job #{job.id} but no recipient email found.")
            application.status = ApplicationStatus.NEEDS_ACTION
            application.failure_reason = "No valid recruiter/application email address found in job posting."
            attempt.status = "FAILED"
            attempt.error_message = application.failure_reason
            attempt.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await notification_service.notify_application_failed(
                db=db, user_id=user.id, company=job.company, role=job.title,
                app_id=application.id, error="Missing recipient email address."
            )
            return {
                "success": False,
                "status": ApplicationStatus.NEEDS_ACTION,
                "message": "Missing recipient email address. Manual action required.",
                "application_id": application.id,
            }

        # 2. Generate grounded application email
        email_content: ApplicationEmailContent = await gemini_provider.generate_application_email(
            candidate_name=profile.full_name or "Candidate",
            candidate_email=user.email,
            candidate_skills=user_skills,
            candidate_bio=profile.bio or "",
            company=job.company,
            role=job.title,
            recipient_name=None,
            job_description=job.description,
        )

        subject = application.email_subject or email_content.subject
        body_text = email_content.body_text
        body_html = email_content.body_html

        if is_dry_run:
            application.status = ApplicationStatus.REVIEW_REQUESTED
            application.submission_method = "DRY_RUN_EMAIL"
            attempt.status = "SUCCESS"
            attempt.external_reference = "DRY_RUN_DISPATCH"
            attempt.completed_at = datetime.now(timezone.utc)

            # Still record the exact email that WOULD have been sent, so a human
            # reviewer can audit it. Nothing is transmitted and sent_at stays NULL.
            db.add(
                OutboundEmail(
                    user_id=user.id,
                    application_id=application.id,
                    event_id=f"EVT-APP-{application.id}",
                    idempotency_key=idempotency_key,
                    email_type="APPLICATION",
                    recipient_email=recipient_email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    status="DRY_RUN_NOT_SENT",
                    message_id="",
                    sent_at=None,
                )
            )
            await db.commit()
            return {
                "success": True,
                "status": "WOULD_SEND_EMAIL",
                "message": f"DRY RUN: Generated email for {recipient_email} ({job.title} at {job.company})",
                "application_id": application.id,
                "recipient": recipient_email,
            }

        # 3. Dispatch and track outbound email
        outbound = await notification_service.send_and_track_email(
            db=db,
            user_id=user.id,
            application_id=application.id,
            event_id=f"EVT-APP-{application.id}",
            email_type="APPLICATION",
            recipient_email=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            idempotency_key=idempotency_key,
        )

        # 4. Record transition
        prev_state = application.status
        application.status = ApplicationStatus.EMAIL_SENT
        application.applied_at = datetime.now(timezone.utc)
        application.submitted_at = datetime.now(timezone.utc)
        application.email_message_id = outbound.message_id or ""
        application.submission_method = "EMAIL"
        job.status = JobStatus.APPLIED

        event = ApplicationEvent(
            application_id=application.id,
            event_type="EMAIL_APPLICATION_SENT",
            previous_state=prev_state,
            new_state=ApplicationStatus.EMAIL_SENT,
            actor="EMAIL_APPLICATION_EXECUTOR",
            details={"recipient": recipient_email, "message_id": outbound.message_id},
        )
        db.add(event)

        attempt.status = "SUCCESS"
        attempt.external_reference = outbound.message_id or ""
        attempt.completed_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(application)

        # Notify user of successful submission
        await notification_service.notify_email_application_sent(
            db=db, user_id=user.id, company=job.company, role=job.title,
            app_id=application.id, recipient_email=recipient_email
        )

        return {
            "success": True,
            "status": ApplicationStatus.EMAIL_SENT,
            "message": f"Application email successfully dispatched to {recipient_email}.",
            "application_id": application.id,
            "message_id": outbound.message_id,
        }


class AuthorizedAPIApplicationExecutor:
    """Submits to official ATS / Platform API endpoints when authorized."""

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        user: User,
        job: Job,
        application: Application,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        attempt_number = (application.retry_count or 0) + 1
        idempotency_key = f"API-{user.id}-{job.id}-{attempt_number}"

        attempt = ExecutionAttempt(
            application_id=application.id,
            attempt_number=attempt_number,
            idempotency_key=idempotency_key,
            submission_method="AUTHORIZED_API",
            status="IN_PROGRESS",
            started_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        await db.commit()

        if dry_run or settings.DRY_RUN:
            application.status = ApplicationStatus.REVIEW_REQUESTED
            attempt.status = "SUCCESS"
            attempt.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "success": True,
                "status": "WOULD_SUBMIT_API",
                "message": f"DRY RUN: Would call official API for {job.title} at {job.company}",
                "application_id": application.id,
            }

        # Platform API requires verified direct integration
        application.status = ApplicationStatus.NEEDS_ACTION
        application.submission_method = "MANUAL_REQUIRED"
        attempt.status = "FAILED"
        attempt.error_message = "Direct ATS API key not configured. Falling back to manual portal completion."
        attempt.completed_at = datetime.now(timezone.utc)

        event = ApplicationEvent(
            application_id=application.id,
            event_type="API_SUBMISSION_FALLBACK",
            previous_state=application.status,
            new_state=ApplicationStatus.NEEDS_ACTION,
            actor="AUTHORIZED_API_EXECUTOR",
            details={"reason": "No direct ATS integration configured"},
        )
        db.add(event)
        await db.commit()

        return {
            "success": True,
            "status": ApplicationStatus.NEEDS_ACTION,
            "message": f"Official API credentials not active. Manual submission packet prepared for {job.company}.",
            "application_id": application.id,
        }


class ManualApplicationExecutor:
    """Prepares structured answers, resume download, and job portal link for manual completion."""

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        user: User,
        job: Job,
        application: Application,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        prev_state = application.status

        if dry_run or settings.DRY_RUN:
            # Nothing is submitted. Report the intended action and leave the
            # application awaiting human review.
            application.status = ApplicationStatus.REVIEW_REQUESTED
            application.submission_method = "DRY_RUN_MANUAL"
            db.add(
                ApplicationEvent(
                    application_id=application.id,
                    event_type="MANUAL_APPLICATION_DRY_RUN",
                    previous_state=prev_state,
                    new_state=ApplicationStatus.REVIEW_REQUESTED,
                    actor="MANUAL_EXECUTOR",
                    details={"portal_url": job.job_url, "note": "DRY RUN - not submitted"},
                )
            )
            await db.commit()
            return {
                "success": True,
                "status": "WOULD_SUBMIT",
                "message": f"DRY RUN: Would prepare manual submission packet for {job.title} at {job.company} ({job.job_url})",
                "application_id": application.id,
            }

        application.status = ApplicationStatus.NEEDS_ACTION
        application.submission_method = "MANUAL"

        event = ApplicationEvent(
            application_id=application.id,
            event_type="MANUAL_APPLICATION_PREPARED",
            previous_state=prev_state,
            new_state=ApplicationStatus.NEEDS_ACTION,
            actor="MANUAL_EXECUTOR",
            details={"portal_url": job.job_url},
        )
        db.add(event)
        await db.commit()

        await notification_service.create_notification(
            db=db,
            user_id=user.id,
            title=f"Action Required: {job.title} — {job.company}",
            message=f"Application materials prepared. Please open the job portal to submit:\n{job.job_url}",
            level=NotificationLevel.ACTION_REQUIRED,
            link=f"/applications?id={application.id}",
            event_type=NotificationEvent.APPLICATION_NEEDS_ACTION,
        )

        return {
            "success": True,
            "status": ApplicationStatus.NEEDS_ACTION,
            "message": f"Application materials ready for manual submission to {job.company}.",
            "application_id": application.id,
        }


class ApplicationExecutor:
    """
    Central Application Executor orchestrating state machine transitions,
    idempotency checks, submission locks, and routing to specialized executors.
    """

    TERMINAL_STATES = ApplicationStatus.terminal_states()

    @classmethod
    def can_submit(cls, status: str) -> bool:
        return ApplicationStatus.can_submit(status)

    @classmethod
    def generate_idempotency_key(cls, user_id: int, job_id: int) -> str:
        raw = f"{user_id}:{job_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    async def acquire_submission_lock(cls, db: AsyncSession, app: Application) -> bool:
        lock_timeout = settings.SCHEDULER_LOCK_TIMEOUT_SECONDS
        now = datetime.now(timezone.utc)
        lock_expiry = now + timedelta(seconds=lock_timeout)

        if app.submission_lock_until and app.submission_lock_until > now:
            remaining = (app.submission_lock_until - now).total_seconds()
            if remaining > 0:
                logger.warning(f"Submission lock active for app {app.id}, {remaining:.0f}s remaining")
                return False

        app.submission_lock_until = lock_expiry
        await db.flush()
        return True

    @classmethod
    async def release_submission_lock(cls, db: AsyncSession, app: Application):
        app.submission_lock_until = None
        await db.flush()

    @classmethod
    async def prepare_application(
        cls, db: AsyncSession, user: User, job_id: int, resume_id: Optional[int] = None
    ) -> Application:
        """Prepares application package and tailored cover letter."""
        from app.services.application_service import application_service
        return await application_service.prepare_application(
            db=db, user=user, job_id=job_id, resume_id=resume_id
        )

    @classmethod
    async def prepare(cls, db: AsyncSession, user: User, job_id: int, resume_id: Optional[int] = None) -> Application:
        """Backwards-compatible alias for :meth:`prepare_application`."""
        return await cls.prepare_application(db, user, job_id, resume_id)

    @classmethod
    async def submit(
        cls,
        db: AsyncSession,
        user: User,
        job: Job,
        application: Application,
        dry_run: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Submits an application with full idempotency, state transitions, and executor routing.
        """
        is_dry = settings.DRY_RUN if dry_run is None else dry_run

        # 0. Master safety gate. AUTO_SUBMIT_ENABLED defaults to False, so no
        # real submission can occur unless an operator explicitly opts in.
        # DRY_RUN always wins over an accidental True elsewhere.
        if not is_dry and not settings.AUTO_SUBMIT_ENABLED:
            is_dry = True
            logger.warning(
                "Submission suppressed: AUTO_SUBMIT_ENABLED is False. "
                "Falling back to dry-run behaviour."
            )
        if not is_dry and settings.REQUIRE_HUMAN_APPROVAL:
            logger.info("Human approval is required; suppressing unattended submission.")
            is_dry = True

        # 1. Idempotency & Terminal state check
        if application.status in cls.TERMINAL_STATES:
            return {
                "success": False,
                "status": application.status,
                "message": f"Application already in terminal state: {application.status}",
                "application_id": application.id,
            }

        # 2. Acquire lock
        lock_ok = await cls.acquire_submission_lock(db, application)
        if not lock_ok:
            return {
                "success": False,
                "status": ApplicationStatus.SUBMISSION_STARTED,
                "message": "Submission lock active. Another worker is processing this application.",
                "application_id": application.id,
            }

        try:
            # Load candidate profile and skills
            prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user.id))
            profile = prof_res.scalar_one_or_none()
            if not profile:
                profile = UserProfile(user_id=user.id, full_name=user.email.split("@")[0])

            skills_res = await db.execute(select(Skill).where(Skill.user_id == user.id))
            user_skills = [s.name for s in skills_res.scalars().all()]

            # 3. Determine routing based on application method
            method = (application.application_method or "").lower()
            if not method or method == "unknown":
                if "email" in job.description.lower() or "@" in job.description:
                    method = "email"
                else:
                    method = "manual"

            if method == "email":
                res = await EmailApplicationExecutor.execute(
                    db=db, user=user, job=job, application=application,
                    profile=profile, user_skills=user_skills, dry_run=is_dry
                )
            elif method == "authorized_api":
                res = await AuthorizedAPIApplicationExecutor.execute(
                    db=db, user=user, job=job, application=application, dry_run=is_dry
                )
            else:
                res = await ManualApplicationExecutor.execute(
                    db=db, user=user, job=job, application=application, dry_run=is_dry
                )

            await cls.release_submission_lock(db, application)
            return res

        except Exception as e:
            logger.error(f"Execution error for application #{application.id}: {e}")
            application.status = ApplicationStatus.FAILED
            application.failure_reason = str(e)
            application.retry_count = (application.retry_count or 0) + 1
            await cls.release_submission_lock(db, application)
            await db.commit()
            return {
                "success": False,
                "status": ApplicationStatus.FAILED,
                "message": f"Execution failed: {e}",
                "application_id": application.id,
            }

    @classmethod
    async def approve_application(
        cls,
        db: AsyncSession,
        application_id: int,
        user_id: int,
        edited_cover_letter: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Application:
        """Processes Human Approval and transitions state to APPROVED -> Executes Router."""
        app_res = await db.execute(
            select(Application).where(Application.id == application_id, Application.user_id == user_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ValueError(f"Application #{application_id} not found")

        prev_state = application.status
        application.is_user_approved = True
        application.approved_at = datetime.now(timezone.utc)
        application.status = ApplicationStatus.APPROVED
        if edited_cover_letter:
            application.cover_letter_text = edited_cover_letter
        if notes:
            application.notes = notes

        # Save Review Record
        review = ApplicationReview(
            application_id=application.id,
            user_id=user_id,
            review_decision="APPROVED",
            feedback_notes=notes or "",
            edited_cover_letter=edited_cover_letter,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)

        event = ApplicationEvent(
            application_id=application.id,
            event_type="APPLICATION_APPROVED",
            previous_state=prev_state,
            new_state=ApplicationStatus.APPROVED,
            actor="USER",
            details={"approved_by": user_id},
        )
        db.add(event)
        await db.commit()
        await db.refresh(application)

        # Notify
        job_res = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_res.scalar_one_or_none()
        if job:
            await notification_service.create_notification(
                db=db,
                user_id=user_id,
                application_id=application.id,
                title=f"Application Approved: {job.title}",
                message=f"You approved the application for {job.title} at {job.company}. Submission workflow engaged.",
                level=NotificationLevel.INFO,
                event_type=NotificationEvent.APPLICATION_APPROVED,
                link=f"/applications?id={application.id}",
            )

        return application

    @classmethod
    async def reject_application(
        cls,
        db: AsyncSession,
        application_id: int,
        user_id: int,
        reason: Optional[str] = None,
    ) -> Application:
        """Processes Human Rejection and transitions state to REJECTED."""
        app_res = await db.execute(
            select(Application).where(Application.id == application_id, Application.user_id == user_id)
        )
        application = app_res.scalar_one_or_none()
        if not application:
            raise ValueError(f"Application #{application_id} not found")

        prev_state = application.status
        application.is_user_approved = False
        application.status = ApplicationStatus.REJECTED
        application.failure_reason = reason or "Rejected by user during human review"

        review = ApplicationReview(
            application_id=application.id,
            user_id=user_id,
            review_decision="REJECTED",
            feedback_notes=reason or "",
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(review)

        event = ApplicationEvent(
            application_id=application.id,
            event_type="APPLICATION_REJECTED",
            previous_state=prev_state,
            new_state=ApplicationStatus.REJECTED,
            actor="USER",
            details={"rejection_reason": reason},
        )
        db.add(event)

        job_res = await db.execute(select(Job).where(Job.id == application.job_id))
        job = job_res.scalar_one_or_none()
        if job:
            job.status = JobStatus.REJECTED

        await db.commit()
        await db.refresh(application)

        if job:
            await notification_service.create_notification(
                db=db,
                user_id=user_id,
                application_id=application.id,
                title=f"Application Rejected: {job.title}",
                message=f"Application for {job.title} at {job.company} was marked REJECTED.",
                level=NotificationLevel.INFO,
                event_type=NotificationEvent.APPLICATION_REJECTED,
                link=f"/applications?id={application.id}",
            )

        return application


application_executor = ApplicationExecutor()