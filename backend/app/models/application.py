from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, Text, JSON, ForeignKey, Float, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class ApplicationStatus:
    # Canonical 9-state machine (spec-aligned)
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    NEEDS_ACTION = "NEEDS_ACTION"
    REJECTED = "REJECTED"

    # Legacy / extended states retained for backwards compatibility
    DISCOVERED = "DISCOVERED"
    NORMALIZED = "NORMALIZED"
    MATCHED = "MATCHED"
    PREPARED = "PREPARED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    APPROVED = "APPROVED"
    SUBMISSION_STARTED = "SUBMISSION_STARTED"
    EMAIL_SENT = "EMAIL_SENT"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    SAVED = "SAVED"
    PREPARING = "PREPARING"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    ARCHIVED = "ARCHIVED"
    OFFER = "OFFER"
    WITHDRAWN = "WITHDRAWN"

    @classmethod
    def terminal_states(cls) -> set:
        return {
            cls.SUBMITTED, cls.VERIFIED, cls.APPLIED, cls.EMAIL_SENT,
            cls.REJECTED, cls.FAILED, cls.NEEDS_ACTION, cls.DUPLICATE_SKIPPED,
            cls.ARCHIVED, cls.WITHDRAWN, cls.INTERVIEW, cls.OFFER
        }

    @classmethod
    def can_submit(cls, status: str) -> bool:
        return status not in cls.terminal_states() and status not in {cls.SUBMISSION_STARTED, cls.SUBMITTING}

class Application(Base):
    __tablename__ = "applications"
    # DB-level guarantee: one application per (user, job) — prevents duplicates
    # even under concurrent/retry execution of the hourly worker.
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
        Index("ix_applications_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default=ApplicationStatus.PREPARED, index=True)
    decision: Mapped[str] = mapped_column(String(50), default="HUMAN_REVIEW")  # HIGH_MATCH, HUMAN_REVIEW, LOW_MATCH
    application_method: Mapped[str] = mapped_column(String(50), default="manual")  # email, authorized_api, manual, unknown
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Idempotency & Lock
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True, default="")
    submission_lock_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # AI Tailored Application Package
    cover_letter_text: Mapped[str] = mapped_column(Text, default="")
    tailored_resume_bullets: Mapped[list] = mapped_column(JSON, default=list)
    custom_pitch: Mapped[str] = mapped_column(Text, default="")
    
    # Email Application Specific Data
    email_recipient: Mapped[str] = mapped_column(String(255), default="")
    email_subject: Mapped[str] = mapped_column(String(500), default="")
    email_message_id: Mapped[str] = mapped_column(String(255), default="")
    
    # Source & Submission
    source: Mapped[str] = mapped_column(String(100), default="")
    submission_method: Mapped[str] = mapped_column(String(50), default="MANUAL_APPROVED")  # EMAIL, AUTHORIZED_API, MANUAL_APPROVED, DRY_RUN
    external_application_id: Mapped[str] = mapped_column(String(255), default="")
    automation_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    is_user_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    
    # Verification & Artifacts
    screenshot_path: Mapped[str] = mapped_column(String(500), default="")
    portal_submission_type: Mapped[str] = mapped_column(String(50), default="MANUAL_APPROVED")
    
    # Followup & notes
    interview_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    salary_offered: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    answers: Mapped[List["ApplicationAnswer"]] = relationship("ApplicationAnswer", back_populates="application", cascade="all, delete-orphan")
    packages: Mapped[List["ApplicationPackage"]] = relationship("ApplicationPackage", back_populates="application", cascade="all, delete-orphan")
    reviews: Mapped[List["ApplicationReview"]] = relationship("ApplicationReview", back_populates="application", cascade="all, delete-orphan")
    events: Mapped[List["ApplicationEvent"]] = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan")
    attempts: Mapped[List["ExecutionAttempt"]] = relationship("ExecutionAttempt", back_populates="application", cascade="all, delete-orphan")

class ApplicationPackage(Base):
    __tablename__ = "application_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    cover_letter_text: Mapped[str] = mapped_column(Text, default="")
    tailored_resume_bullets: Mapped[list] = mapped_column(JSON, default=list)
    custom_pitch: Mapped[str] = mapped_column(Text, default="")
    email_body_text: Mapped[str] = mapped_column(Text, default="")
    email_subject: Mapped[str] = mapped_column(String(500), default="")
    recipient_email: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    application: Mapped["Application"] = relationship("Application", back_populates="packages")

class ApplicationReview(Base):
    __tablename__ = "application_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    review_decision: Mapped[str] = mapped_column(String(50), nullable=False)  # APPROVED, REJECTED, EDITED
    feedback_notes: Mapped[str] = mapped_column(Text, default="")
    edited_cover_letter: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    application: Mapped["Application"] = relationship("Application", back_populates="reviews")

class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(50), default="")
    new_state: Mapped[str] = mapped_column(String(50), default="")
    actor: Mapped[str] = mapped_column(String(100), default="SYSTEM")  # SYSTEM, USER, GEMINI_DECISION_ENGINE, EXECUTOR
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    application: Mapped["Application"] = relationship("Application", back_populates="events")

class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    idempotency_key: Mapped[str] = mapped_column(String(128), index=True, default="")
    submission_method: Mapped[str] = mapped_column(String(50), default="MANUAL")
    status: Mapped[str] = mapped_column(String(50), default="IN_PROGRESS")  # IN_PROGRESS, SUCCESS, FAILED, RETRYING
    external_reference: Mapped[str] = mapped_column(String(255), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    application: Mapped["Application"] = relationship("Application", back_populates="attempts")

class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_edited_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="MOTIVATION")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    application: Mapped["Application"] = relationship("Application", back_populates="answers")