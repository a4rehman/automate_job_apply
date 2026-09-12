from typing import List, Dict, Any, Optional
from app.job_sources.base import JobSource, NormalizedJob

class IndeedAdapter(JobSource):
    """Indeed Adapter - Compliance first, official XML/Publisher feed or manual URL import only."""
    def __init__(self):
        super().__init__(name="Indeed", source_type="ADAPTER")
        self.rate_limit_rpm = 15
        self.requires_auth = False
        self.supports_auto_submit = False
        self.requires_user_approval = True
        self.api_status = "PUBLISHER_API_ONLY"

    async def fetch_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def normalize_job(self, raw_job: Dict[str, Any]) -> Optional[NormalizedJob]:
        return None

class GlassdoorAdapter(JobSource):
    """Glassdoor Adapter - Compliance first, partner API only."""
    def __init__(self):
        super().__init__(name="Glassdoor", source_type="ADAPTER")
        self.rate_limit_rpm = 10
        self.requires_auth = True
        self.supports_auto_submit = False
        self.requires_user_approval = True
        self.api_status = "PARTNER_API_ONLY"

    async def fetch_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def normalize_job(self, raw_job: Dict[str, Any]) -> Optional[NormalizedJob]:
        return None

class WellfoundAdapter(JobSource):
    """Wellfound (AngelList) Adapter - Compliance first, official startup job alerts."""
    def __init__(self):
        super().__init__(name="Wellfound", source_type="ADAPTER")
        self.rate_limit_rpm = 15
        self.requires_auth = True
        self.supports_auto_submit = False
        self.requires_user_approval = True
        self.api_status = "OFFICIAL_INTEGRATION"

    async def fetch_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    async def normalize_job(self, raw_job: Dict[str, Any]) -> Optional[NormalizedJob]:
        return None
