from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AutomationSettingsUpdate(BaseModel):
    is_scheduler_enabled: Optional[bool] = None
    monitoring_interval_minutes: Optional[int] = Field(None, ge=5, le=1440)
    min_match_score: Optional[float] = Field(None, ge=0, le=100)
    high_match_threshold: Optional[float] = Field(None, ge=0, le=100)
    auto_prepare_applications: Optional[bool] = None
    require_human_approval: Optional[bool] = None
    notification_channels: Optional[Dict[str, bool]] = None
    enabled_sources: Optional[List[str]] = None

class AutomationSettingsResponse(BaseModel):
    id: int
    user_id: int
    is_scheduler_enabled: bool
    monitoring_interval_minutes: int
    min_match_score: float
    high_match_threshold: float
    auto_prepare_applications: bool
    require_human_approval: bool
    notification_channels: Dict[str, bool]
    enabled_sources: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ManualRunResponse(BaseModel):
    status: str
    message: str
    jobs_discovered: int
    jobs_analyzed: int
    applications_prepared: int
