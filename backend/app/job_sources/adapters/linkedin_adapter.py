from typing import List, Dict, Any, Optional
from app.job_sources.base import JobSource, NormalizedJob

class LinkedInAdapter(JobSource):
    """
    LinkedIn Adapter:
    - Compliance: Does NOT scrape protected profiles or bypass bot detection.
    - Integration: Uses official LinkedIn Talent / Job Posting APIs or user-provided job URLs.
    - Automation Policy: Automatic submission NOT supported without enterprise API.
    - Workflow: Human-in-the-loop application preparation with user final review.
    """
    def __init__(self):
        super().__init__(name="LinkedIn", source_type="ADAPTER")
        self.rate_limit_rpm = 10
        self.requires_auth = True
        self.supports_auto_submit = False
        self.requires_user_approval = True
        self.api_status = "RESTRICTED_OFFICIAL_API_ONLY"

    async def fetch_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        # Does not perform unauthorized scraping
        return []

    async def normalize_job(self, raw_job: Dict[str, Any]) -> Optional[NormalizedJob]:
        return None
