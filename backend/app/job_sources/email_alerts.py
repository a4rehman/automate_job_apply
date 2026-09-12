import re
from typing import List, Dict, Any, Optional
from app.job_sources.base import JobSource, NormalizedJob
from app.core.logging_config import logger

class EmailAlertJobSource(JobSource):
    """
    Parser for email job alerts received via forward or IMAP.
    Converts email notification body into structured NormalizedJob items.
    """
    def __init__(self):
        super().__init__(name="Email Job Alerts", source_type="EMAIL")
        self.requires_auth = True
        self.supports_auto_submit = False
        self.requires_user_approval = True

    async def fetch_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        # Placeholder for IMAP client integration or webhook ingestion
        return []

    async def normalize_job(self, email_payload: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            subject = email_payload.get("subject", "")
            body = email_payload.get("body", "")
            
            # Simple heuristic parsing of email alerts
            title_match = re.search(r'New Job Alert:\s*(.+?)\s+at\s+(.+)', subject, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
                company = title_match.group(2).strip()
            else:
                title = subject or "Job Alert Position"
                company = "Alert Source"

            url_match = re.search(r'https?://[^\s<>"]+', body)
            job_url = url_match.group(0) if url_match else ""

            return NormalizedJob(
                title=title,
                company=company,
                location="Remote",
                remote_type="REMOTE",
                employment_type="FULL_TIME",
                description=body[:2000],
                job_url=job_url,
                source_name=self.name,
                skills=["Python", "AI"],
                requirements=["Python"],
                preferred_skills=[],
                experience_years_required=2.0
            )
        except Exception as e:
            logger.error(f"Failed to normalize email alert: {e}")
            return None
