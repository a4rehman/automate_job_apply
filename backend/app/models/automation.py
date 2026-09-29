from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, JSON, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class AutomationSettings(Base):
    __tablename__ = "automation_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    automation_mode: Mapped[str] = mapped_column(String(50), default="SAFE_MODE")  # SAFE_MODE, ASSISTED_MODE, AUTHORIZED_AUTO_MODE
    is_scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    monitoring_interval_minutes: Mapped[int] = mapped_column(Integer, default=10)  # 5, 10, 15, 30, 60
    
    min_match_score: Mapped[float] = mapped_column(Float, default=75.0)
    high_match_threshold: Mapped[float] = mapped_column(Float, default=85.0)
    review_threshold: Mapped[float] = mapped_column(Float, default=70.0)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.60)
    
    auto_prepare_applications: Mapped[bool] = mapped_column(Boolean, default=True)  # Prepare package if >= min_match_score
    require_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)  # Strict human in loop
    
    max_daily_applications: Mapped[int] = mapped_column(Integer, default=30)
    max_applications_per_run: Mapped[int] = mapped_column(Integer, default=10)
    
    notification_channels: Mapped[dict] = mapped_column(JSON, default=lambda: {
        "in_app": True,
        "email": True,
        "telegram": False
    })
    
    enabled_sources: Mapped[list] = mapped_column(JSON, default=lambda: [
        # RemoteOK is intentionally absent: its feed returns HTTP 410 Gone.
        "WeWorkRemotely RSS",
        "Remotive API",
        "Arbeitnow API"
    ])
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship("User", back_populates="automation_settings")

