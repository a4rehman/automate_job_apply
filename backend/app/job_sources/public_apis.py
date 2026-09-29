import re
from typing import List, Dict, Any, Optional
import httpx
from app.job_sources.base import JobSource, NormalizedJob
from app.core.logging_config import logger


def _extract_experience_years(text: str) -> float:
    patterns = [
        r"(\d+)\s*\+\s*years?",
        r"(\d+)\s*(?:to|-)\s*\d+\s*years?",
        r"minimum of\s+(\d+)\s*years?",
        r"at least\s+(\d+)\s*years?",
        r"(\d+)\s*years? of experience",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return 0.0


class RemotiveAPISource(JobSource):
    def __init__(self):
        super().__init__(name="Remotive API", source_type="API")
        self.endpoint = "https://remotive.com/api/remote-jobs"

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        async def _do_fetch() -> List[Dict[str, Any]]:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(f"{self.endpoint}?category=software-dev&limit={limit}")
                res.raise_for_status()
                data = res.json()
                return data.get("jobs", [])[:limit]

        return await self._retry(_do_fetch, "remotive_fetch")

    async def normalize_job(self, raw: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            clean_desc = re.sub(r'<[^>]+>', ' ', raw.get("description", ""))
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            tags = [t for t in raw.get("tags", []) if isinstance(t, str) and t.strip()]

            return NormalizedJob(
                title=raw.get("title", "Software Developer"),
                company=raw.get("company_name", "Unknown"),
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
                requirements=tags[:3],
                preferred_skills=tags[3:],
                experience_years_required=_extract_experience_years(clean_desc)
            )
        except Exception as e:
            logger.error(f"Error normalizing Remotive job: {e}")
            return None

class ArbeitnowAPISource(JobSource):
    def __init__(self):
        super().__init__(name="Arbeitnow API", source_type="API")
        self.endpoint = "https://www.arbeitnow.com/api/job-board-api"

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        async def _do_fetch() -> List[Dict[str, Any]]:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(self.endpoint)
                res.raise_for_status()
                data = res.json()
                return data.get("data", [])[:limit]

        return await self._retry(_do_fetch, "arbeitnow_fetch")

    async def normalize_job(self, raw: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            clean_desc = re.sub(r'<[^>]+>', ' ', raw.get("description", ""))
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            tags = [t for t in raw.get("tags", []) if isinstance(t, str) and t.strip()]

            return NormalizedJob(
                title=raw.get("title", "Engineer"),
                company=raw.get("company_name", "Unknown"),
                location=raw.get("location", "Remote"),
                remote_type="REMOTE" if raw.get("remote", True) else "HYBRID",
                employment_type="FULL_TIME",
                description=clean_desc,
                job_url=raw.get("url", ""),
                external_job_id=raw.get("slug", ""),
                source_name=self.name,
                skills=tags,
                requirements=tags[:4],
                preferred_skills=tags[4:],
                experience_years_required=_extract_experience_years(clean_desc)
            )
        except Exception as e:
            logger.error(f"Error normalizing Arbeitnow job: {e}")
            return None

def get_public_api_sources() -> List[JobSource]:
    return [RemotiveAPISource(), ArbeitnowAPISource()]
