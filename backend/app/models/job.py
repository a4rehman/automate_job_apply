from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, Text, JSON, ForeignKey, Float
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

class JobSourceConfig(Base):
    __tablename__ = "job_source_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False) # RSS, API, EMAIL, CSV, ADAPTER
    url_or_endpoint: Mapped[str] = mapped_column(String(500), default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=30)
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_auto_submit: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="source_config")

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job_source_configs.id", ondelete="SET NULL"), nullable=True)
    source_name: Mapped[str] = mapped_column(String(100), default="DIRECT_IMPORT", index=True)
    external_job_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), default="Remote")
    remote_type: Mapped[str] = mapped_column(String(50), default="REMOTE") # REMOTE, HYBRID, ONSITE
    employment_type: Mapped[str] = mapped_column(String(50), default="FULL_TIME") # FULL_TIME, CONTRACT, PART_TIME
    salary_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    salary_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False) # SHA-256 for duplicate detection
    requirements: Mapped[list] = mapped_column(JSON, default=list) # Extracted required items
    preferred_skills: Mapped[list] = mapped_column(JSON, default=list)
    skills: Mapped[list] = mapped_column(JSON, default=list) # Unified extracted skills
    experience_years_required: Mapped[float] = mapped_column(Float, default=0.0)
    
    job_url: Mapped[str] = mapped_column(String(1000), default="")
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detected_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    status: Mapped[str] = mapped_column(String(50), default=JobStatus.NEW, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    source_config: Mapped[Optional["JobSourceConfig"]] = relationship("JobSourceConfig", back_populates="jobs")
    matches: Mapped[List["JobMatch"]] = relationship("JobMatch", back_populates="job", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="job", cascade="all, delete-orphan")

class JobMatch(Base):
    __tablename__ = "job_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    overall_score: Mapped[float] = mapped_column(Float, default=0.0) # 0-100%
    skills_score: Mapped[float] = mapped_column(Float, default=0.0) # 35% weight
    role_score: Mapped[float] = mapped_column(Float, default=0.0)   # 25% weight
    experience_score: Mapped[float] = mapped_column(Float, default=0.0) # 15% weight
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)   # 15% weight
    location_score: Mapped[float] = mapped_column(Float, default=0.0)   # 5% weight
    salary_score: Mapped[float] = mapped_column(Float, default=0.0)     # 5% weight
    
    matching_skills: Mapped[list] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list] = mapped_column(JSON, default=list)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(String(50), default="RECOMMENDED") # HIGH_PRIORITY, RECOMMENDED, NOT_RECOMMENDED
    
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    job: Mapped["Job"] = relationship("Job", back_populates="matches")
