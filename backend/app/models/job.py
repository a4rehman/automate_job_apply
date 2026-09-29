from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, Text, JSON, ForeignKey, Float, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class JobStatus:
    NEW = "NEW"
    ANALYZED = "ANALYZED"
    HIGH_MATCH = "HIGH_MATCH"
    LOW_MATCH = "LOW_MATCH"
    APPLICATION_READY = "APPLICATION_READY"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    NEEDS_ACTION = "NEEDS_ACTION"
    SUBMITTING = "SUBMITTING"

class JobSourceHealth:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"

class JobSourceConfig(Base):
    __tablename__ = "job_source_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    url_or_endpoint: Mapped[str] = mapped_column(String(500), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=30)
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_auto_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    health_status: Mapped[str] = mapped_column(String(20), default=JobSourceHealth.HEALTHY)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="source_config")

class Job(Base):
    __tablename__ = "jobs"
    # DB-level idempotency guards (belt-and-braces with app-level dedup):
    #  - content hash is always present -> hard unique
    #  - source + external_job_id unique so the same listing from one source
    #    can never be inserted twice, even on worker retry
    __table_args__ = (
        UniqueConstraint("description_hash", name="uq_jobs_description_hash"),
        # Partial unique index: only constrain rows that actually carry an
        # external id. Manual/CSV imports legitimately store '' and must not
        # collide with each other.
        Index(
            "uq_jobs_source_external",
            "source_name",
            "external_job_id",
            unique=True,
            sqlite_where=text("external_job_id != ''"),
            postgresql_where=text("external_job_id != ''"),
        ),
        Index("ix_jobs_status_score", "status", "match_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_source_configs.id", ondelete="SET NULL"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(100), default="DIRECT_IMPORT", index=True)
    external_job_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), default="Remote")
    remote_type: Mapped[str] = mapped_column(String(50), default="REMOTE")
    employment_type: Mapped[str] = mapped_column(String(50), default="FULL_TIME")
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    requirements: Mapped[list] = mapped_column(JSON, default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_years_required: Mapped[float] = mapped_column(Float, default=0.0)
    
    job_url: Mapped[str] = mapped_column(String(1000), default="")
    normalized_url: Mapped[str] = mapped_column(String(1000), default="")
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.NEW, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    source_config: Mapped[Optional["JobSourceConfig"]] = relationship("JobSourceConfig", back_populates="jobs")
    matches: Mapped[List["JobMatch"]] = relationship("JobMatch", back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    job_requirements: Mapped[List["JobRequirement"]] = relationship("JobRequirement", back_populates="job", cascade="all, delete-orphan")

class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_type: Mapped[str] = mapped_column(String(50), default="TECHNICAL")  # TECHNICAL, EXPERIENCE, EDUCATION, SOFT, CERTIFICATION
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    extracted_experience_years: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["Job"] = relationship("Job", back_populates="job_requirements")

class JobMatch(Base):
    __tablename__ = "job_matches"
    # One match per (job, user) — safe under worker retries
    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="uq_job_matches_job_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    skills_score: Mapped[float] = mapped_column(Float, default=0.0)
    role_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    seniority_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    salary_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    
    matching_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    concerns: Mapped[list] = mapped_column(JSON, default=list)
    hard_requirements_failed: Mapped[list] = mapped_column(JSON, default=list)
    
    application_method: Mapped[str] = mapped_column(String(50), default="unknown")  # email, authorized_api, manual, unknown
    decision: Mapped[str] = mapped_column(String(50), default="HUMAN_REVIEW")  # HIGH_MATCH, HUMAN_REVIEW, LOW_MATCH
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    
    reasoning: Mapped[str] = mapped_column(Text, default="")
    match_reasons: Mapped[list] = mapped_column(JSON, default=list)
    recommendation: Mapped[str] = mapped_column(String(50), default="RECOMMENDED")
    
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["Job"] = relationship("Job", back_populates="matches")

class RunStatus:
    """Lifecycle states for an automation cycle (Phase 5)."""
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    # Cycle could not start: no user configured, or the profile is too
    # incomplete to match against anything. Distinct from FAILED, which means
    # real work was attempted and broke.
    INCOMPLETE = "INCOMPLETE"

    @classmethod
    def terminal(cls) -> set:
        return {cls.SUCCESS, cls.PARTIAL_SUCCESS, cls.FAILED, cls.SKIPPED, cls.INCOMPLETE}

    @classmethod
    def from_outcome(cls, prepared: int, submitted: int, failures: int) -> str:
        """Derive a truthful terminal state from actual cycle outcomes."""
        if failures and (prepared or submitted):
            return cls.PARTIAL_SUCCESS
        if failures and not (prepared or submitted):
            return cls.FAILED
        return cls.SUCCESS


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"
    # run_id is the idempotency key for a cycle: the same run can never create
    # two rows, no matter how many times a worker retries.
    __table_args__ = (UniqueConstraint("run_id", name="uq_scheduler_runs_run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.RUNNING, index=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    jobs_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    high_matches: Mapped[int] = mapped_column(Integer, default=0)
    human_reviews: Mapped[int] = mapped_column(Integer, default=0)
    low_matches: Mapped[int] = mapped_column(Integer, default=0)
    applications_prepared: Mapped[int] = mapped_column(Integer, default=0)
    applications_submitted: Mapped[int] = mapped_column(Integer, default=0)
    email_applications: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    notifications_sent: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped[Optional["User"]] = relationship("User", back_populates="scheduler_runs")

class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=JobSourceHealth.HEALTHY)
    last_check_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_fetches: Mapped[int] = mapped_column(Integer, default=0)
    total_failures: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))