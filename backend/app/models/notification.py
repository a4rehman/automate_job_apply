from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class NotificationLevel:
    INFO = "INFO"
    HIGH_MATCH = "HIGH_MATCH"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    ERROR = "ERROR"
    WARNING = "WARNING"

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(50), default=NotificationLevel.INFO)
    link: Mapped[str] = mapped_column(String(500), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user: Mapped["User"] = relationship("User", back_populates="notifications")

class OutboundEmail(Base):
    __tablename__ = "outbound_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    
    email_type: Mapped[str] = mapped_column(String(50), default="APPLICATION")  # APPLICATION, NOTIFICATION, ALERT
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sender_email: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)  # PENDING, SENT, FAILED, DUPLICATE_SKIPPED
    message_id: Mapped[str] = mapped_column(String(255), default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

