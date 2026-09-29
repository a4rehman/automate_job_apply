import asyncio
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from app.core.errors import ErrorType, backoff_delay, classify_error, is_retryable, log_classified_error
from app.core.logging_config import logger


def normalize_url(url: str) -> str:
    import re
    url = (url or "").strip()
    url = re.sub(r'[#?&].*$', '', url)
    url = url.rstrip('/')
    return url.lower()


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
    def normalized_url(self) -> str:
        return normalize_url(self.job_url)

    @property
    def description_hash(self) -> str:
        """SHA-256 hash of normalized title, company, and description for deduplication."""
        seed = f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.description.strip()[:1000]}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

class JobSource(ABC):
    # Network policy (Phase 7): timeout + bounded retries with backoff
    request_timeout_seconds: float = 20.0
    max_retries: int = 3

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

    async def health_check(self) -> Dict[str, Any]:
        """Cheap reachability probe. Never raises — callers record the outcome."""
        try:
            await self.fetch_jobs(limit=1)
            return {"source": self.name, "healthy": True, "error_type": ""}
        except Exception as e:
            etype = log_classified_error(f"health_check:{self.name}", e)
            return {"source": self.name, "healthy": False, "error_type": etype, "error": str(e)[:200]}

    async def _retry(self, coro_factory, context: str):
        """Execute a coroutine with timeout, bounded retry and exponential backoff.

        Only retryable error classes are retried; permanent/auth failures fail
        fast so a misconfigured source never blocks a whole cycle.
        """
        last_exc: Optional[BaseException] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await asyncio.wait_for(coro_factory(), timeout=self.request_timeout_seconds)
            except asyncio.TimeoutError as e:
                last_exc = e
                etype = ErrorType.TRANSIENT
            except Exception as e:
                last_exc = e
                etype = classify_error(e)
                if not is_retryable(etype):
                    log_classified_error(f"{context}:{self.name}", e)
                    raise
            if attempt < self.max_retries:
                delay = backoff_delay(attempt)
                logger.warning(
                    f"[{self.name}] {etype} on attempt {attempt}/{self.max_retries}; "
                    f"retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)

        assert last_exc is not None
        log_classified_error(f"{context}:{self.name}", last_exc)
        raise last_exc
