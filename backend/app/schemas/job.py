from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class JobBase(BaseModel):
    title: str
    company: str
    location: str = "Remote"
    remote_type: str = "REMOTE" # REMOTE, HYBRID, ONSITE
    employment_type: str = "FULL_TIME"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "USD"
    description: str
    job_url: str = ""
    external_job_id: Optional[str] = ""
    source_name: str = "DIRECT_IMPORT"

class JobCreate(JobBase):
    skills: List[str] = []
    requirements: List[str] = []
    preferred_skills: List[str] = []
    experience_years_required: float = 0.0

class JobFilter(BaseModel):
    search: Optional[str] = None
    source: Optional[str] = None
    min_score: Optional[float] = None
    remote_type: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

class JobMatchResponse(BaseModel):
    id: int
    job_id: int
    user_id: int
    overall_score: float
    skills_score: float
    role_score: float
    experience_score: float
    semantic_score: float
    location_score: float
    salary_score: float
    matching_skills: List[str]
    missing_skills: List[str]
    reasoning: str
    recommendation: str
    analyzed_at: datetime

    class Config:
        from_attributes = True

class JobResponse(JobBase):
    id: int
    source_id: Optional[int] = None
    requirements: List[str] = []
    preferred_skills: List[str] = []
    skills: List[str] = []
    experience_years_required: float
    posted_date: Optional[datetime] = None
    detected_date: datetime
    match_score: float
    status: str
    created_at: datetime
    match_details: Optional[JobMatchResponse] = None

    class Config:
        from_attributes = True

class JobSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    url_or_endpoint: str
    is_enabled: bool
    rate_limit_rpm: int
    requires_auth: bool
    supports_auto_submit: bool
    requires_user_approval: bool
    last_polled_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class JobSourceToggle(BaseModel):
    is_enabled: bool

class CSVImportResponse(BaseModel):
    total_parsed: int
    new_jobs_added: int
    duplicates_skipped: int
    errors: List[str] = []
