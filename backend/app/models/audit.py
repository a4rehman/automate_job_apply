from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True) 
    # e.g. JOB_DISCOVERED, JOB_ANALYZED, APPLICATION_PREPARED, USER_APPROVED, APPLICATION_SUBMITTED, ERROR_OCCURRED
    entity_type: Mapped[str] = mapped_column(String(50), default="") # JOB, APPLICATION, RESUME, PROFILE, SETTINGS
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(50), default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
