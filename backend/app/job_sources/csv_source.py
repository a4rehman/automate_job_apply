import csv
import io
import re
from typing import List, Dict, Any, Optional
from app.job_sources.base import JobSource, NormalizedJob
from app.core.logging_config import logger

class CSVJobSource(JobSource):
    def __init__(self):
        super().__init__(name="CSV Import", source_type="CSV")

    async def fetch_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return []

    async def normalize_job(self, raw: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            title = raw.get("title") or raw.get("job_title") or raw.get("position") or "Software Engineer"
            company = raw.get("company") or raw.get("company_name") or "Direct Company"
            description = raw.get("description") or raw.get("job_description") or title
            url = raw.get("url") or raw.get("job_url") or raw.get("link") or ""
            location = raw.get("location") or "Remote"
            remote_type = raw.get("remote_type") or ("REMOTE" if "remote" in location.lower() else "ONSITE")
            
            raw_skills = raw.get("skills", "")
            if isinstance(raw_skills, list):
                skills = raw_skills
            elif isinstance(raw_skills, str):
                skills = [s.strip() for s in re.split(r'[,|;]', raw_skills) if s.strip()]
            else:
                skills = []

            return NormalizedJob(
                title=title,
                company=company,
                location=location,
                remote_type=remote_type,
                employment_type=raw.get("employment_type", "FULL_TIME"),
                salary_min=float(raw["salary_min"]) if raw.get("salary_min") else None,
                salary_max=float(raw["salary_max"]) if raw.get("salary_max") else None,
                currency=raw.get("currency", "USD"),
                description=description,
                job_url=url,
                external_job_id=str(raw.get("id") or raw.get("external_id") or ""),
                source_name="CSV Import",
                skills=skills,
                requirements=skills[:4],
                preferred_skills=skills[4:],
                experience_years_required=float(raw.get("experience_years_required", 2.0))
            )
        except Exception as e:
            logger.error(f"Error normalizing CSV row: {e}")
            return None

    @classmethod
    def parse_csv_content(cls, csv_text: str) -> List[Dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = []
        for row in reader:
            rows.append({k.lower().strip(): v for k, v in row.items()})
        return rows
