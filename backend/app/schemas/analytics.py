from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class DashboardStatsResponse(BaseModel):
    jobs_found_today: int
    high_match_jobs_count: int
    applications_prepared_count: int
    applications_applied_count: int
    interview_count: int
    interview_rate_percentage: float
    total_jobs_tracked: int
    avg_match_score: float

class MatchDistributionItem(BaseModel):
    range_label: str
    count: int

class ApplicationFunnelItem(BaseModel):
    status: str
    label: str
    count: int

class AnalyticsSummaryResponse(BaseModel):
    stats: DashboardStatsResponse
    match_distribution: List[MatchDistributionItem]
    application_funnel: List[ApplicationFunnelItem]
    recent_activity: List[Dict[str, Any]]
