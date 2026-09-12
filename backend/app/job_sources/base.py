import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class NormalizedJob(BaseModel):
    title: str
    company: str
    location: str = "Remote"
    remote_type: str = "REMOTE" # REMOTE, HYBRID, ONSITE
    employment_type: str = "FULL_TIME"
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "USD"
    description: str
    job_url: str
    external_job_id: Optional[str] = ""
    source_name: str
    posted_date: Optional[datetime] = None
    requirements: List[str] = []
    preferred_skills: List[str] = []
    skills: List[str] = []
    experience_years_required: float = 0.0

    @property
    def description_hash(self) -> str:
        """SHA-256 hash of normalized title, company, and description for deduplication."""
        seed = f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.description.strip()[:1000]}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

class JobSource(ABC):
    def __init__(self, name: str, source_type: str):
        self.name = name
        self.source_type = source_type
        self.rate_limit_rpm = 30
        self.requires_auth = False
        self.supports_auto_submit = False
        self.requires_user_approval = True

    @abstractmethod
    async def fetch_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch raw job records from feed, API, or source."""
        pass

    @abstractmethod
    async def normalize_job(self, raw_job: Dict[str, Any]) -> Optional[NormalizedJob]:
        """Normalize raw platform data into standardized NormalizedJob schema."""
        pass
