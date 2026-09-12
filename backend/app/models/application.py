from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Boolean, DateTime, Integer, Text, JSON, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class ApplicationStatus:
    SAVED = "SAVED"
    PREPARING = "PREPARING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"
    WITHDRAWN = "WITHDRAWN"

class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id: Mapped[Optional[int]] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default=ApplicationStatus.SAVED, index=True)
    
    # AI Tailored Application Package
    cover_letter_text: Mapped[str] = mapped_column(Text, default="")
    tailored_resume_bullets: Mapped[list] = mapped_column(JSON, default=list) # List of {original, tailored, reason}
    custom_pitch: Mapped[str] = mapped_column(Text, default="")
    
    # Automation & Verification
    screenshot_path: Mapped[str] = mapped_column(String(500), default="")
    portal_submission_type: Mapped[str] = mapped_column(String(50), default="MANUAL_APPROVED") # API_DIRECT, PLAYWRIGHT_ASSISTED, MANUAL_APPROVED
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    is_user_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Followup & notes
    interview_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    salary_offered: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    answers: Mapped[List["ApplicationAnswer"]] = relationship("ApplicationAnswer", back_populates="application", cascade="all, delete-orphan")

class ApplicationAnswer(Base):
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_edited_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="MOTIVATION") # MOTIVATION, TECHNICAL, EXPERIENCE, GENERAL
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    application: Mapped["Application"] = relationship("Application", back_populates="answers")
