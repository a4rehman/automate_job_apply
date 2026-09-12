import re
from typing import Dict, Any, Optional
from app.job_sources.base import JobSource, NormalizedJob
from app.ai.job_analyzer import job_analyzer
from app.core.logging_config import logger

class ManualJobImporter:
    @staticmethod
    async def import_raw_job(
        title: str,
        company: str,
        description: str,
        job_url: str = "",
        location: str = "Remote",
        remote_type: str = "REMOTE",
        salary_min: Optional[float] = None,
        salary_max: Optional[float] = None
    ) -> NormalizedJob:
        """Parse, extract AI entities, and return normalized job ready for database insertion."""
        # Use AI Job Analyzer to extract skills and requirements
        analysis = await job_analyzer.analyze_job_description(
            title=title,
            company=company,
            description=description
        )

        return NormalizedJob(
            title=title.strip(),
            company=company.strip(),
            location=location.strip() or "Remote",
            remote_type=remote_type.upper(),
            employment_type="FULL_TIME",
            salary_min=salary_min,
            salary_max=salary_max,
            currency="USD",
            description=description.strip(),
            job_url=job_url.strip(),
            external_job_id="",
            source_name="MANUAL_IMPORT",
            skills=analysis.get("skills", []),
            requirements=analysis.get("required_skills", []),
            preferred_skills=analysis.get("preferred_skills", []),
            experience_years_required=analysis.get("experience_years_required", 2.0)
        )
