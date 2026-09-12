import re
from typing import List, Dict, Any, Optional
import httpx
from app.job_sources.base import JobSource, NormalizedJob
from app.core.logging_config import logger

class RemotiveAPISource(JobSource):
    def __init__(self):
        super().__init__(name="Remotive API", source_type="API")
        self.endpoint = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(f"{self.endpoint}?category=software-dev&limit={limit}")
                if res.status_code == 200:
                    data = res.json()
                    return data.get("jobs", [])[:limit]
        except Exception as e:
            logger.error(f"Error fetching from Remotive API: {e}")
        return []

    async def normalize_job(self, raw: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            clean_desc = re.sub(r'<[^>]+>', ' ', raw.get("description", ""))
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            tags = raw.get("tags", [])

            return NormalizedJob(
                title=raw.get("title", "Software Developer"),
                company=raw.get("company_name", "Remotive Company"),
                location=raw.get("candidate_required_location", "Remote"),
                remote_type="REMOTE",
                employment_type=raw.get("job_type", "FULL_TIME").upper(),
                salary_min=None,
                salary_max=None,
                currency="USD",
                description=clean_desc,
                job_url=raw.get("url", ""),
                external_job_id=str(raw.get("id", "")),
                source_name=self.name,
                skills=tags,
                requirements=tags[:3] if tags else ["Python", "FastAPI"],
                preferred_skills=tags[3:] if len(tags) > 3 else ["Docker"],
                experience_years_required=3.0
            )
        except Exception as e:
            logger.error(f"Error normalizing Remotive job: {e}")
            return None

class ArbeitnowAPISource(JobSource):
    def __init__(self):
        super().__init__(name="Arbeitnow API", source_type="API")
        self.endpoint = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(self.endpoint)
                if res.status_code == 200:
                    data = res.json()
                    return data.get("data", [])[:limit]
        except Exception as e:
            logger.error(f"Error fetching from Arbeitnow API: {e}")
        return []

    async def normalize_job(self, raw: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            clean_desc = re.sub(r'<[^>]+>', ' ', raw.get("description", ""))
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            tags = raw.get("tags", [])

            return NormalizedJob(
                title=raw.get("title", "Engineer"),
                company=raw.get("company_name", "Tech Co"),
                location=raw.get("location", "Remote"),
                remote_type="REMOTE" if raw.get("remote", True) else "HYBRID",
                employment_type="FULL_TIME",
                description=clean_desc,
                job_url=raw.get("url", ""),
                external_job_id=raw.get("slug", ""),
                source_name=self.name,
                skills=tags,
                requirements=tags[:4] if tags else ["Python", "Machine Learning"],
                preferred_skills=tags[4:] if len(tags) > 4 else [],
                experience_years_required=2.0
            )
        except Exception as e:
            logger.error(f"Error normalizing Arbeitnow job: {e}")
            return None

def get_public_api_sources() -> List[JobSource]:
    return [RemotiveAPISource(), ArbeitnowAPISource()]
