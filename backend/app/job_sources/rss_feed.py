import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import feedparser
import httpx
from app.job_sources.base import JobSource, NormalizedJob


def _extract_experience_years(text: str) -> float:
    """Best-effort extraction of required experience from a description."""
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
            val = float(m.group(1)) if m.lastindex == 1 else float(m.group(1))
            return val
    return 0.0


class RSSJobSource(JobSource):
    def __init__(self, name: str, feed_url: str):
        super().__init__(name=name, source_type="RSS")
        self.feed_url = feed_url

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        async def _do_fetch() -> List[Dict[str, Any]]:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(self.feed_url, headers={"User-Agent": "Mozilla/5.0 (AI Job Agent)"})
                # Do NOT swallow non-200: the monitor must see a real failure so
                # source health and the cycle outcome stay truthful.
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                return feed.entries[:limit]

        return await self._retry(_do_fetch, "rss_fetch")

    async def normalize_job(self, entry: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")

            # Clean HTML tags
            clean_desc = re.sub(r'<[^>]+>', ' ', summary)
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()

            # Extract company if in title e.g. "Company: Title" or "Title at Company"
            company = entry.get("company") or entry.get("author") or entry.get("source", {}).get("title") or ""
            if not company:
                if " at " in title:
                    parts = title.split(" at ")
                    title = parts[0].strip()
                    company = parts[1].strip()
                elif ":" in title:
                    parts = title.split(":", 1)
                    company = parts[0].strip()
                    title = parts[1].strip()
            company = company.strip() or "Unknown"

            # Extract basic skills from description
            tech_keywords = [
                "Python", "FastAPI", "Machine Learning", "Deep Learning", "LLM",
                "LangChain", "OpenAI", "PyTorch", "TensorFlow", "Pandas", "SQL",
                "Docker", "Kubernetes", "AWS", "RAG", "Vector Databases", "TypeScript", "React"
            ]
            skills = [kw for kw in tech_keywords if re.search(rf'\b{re.escape(kw)}\b', clean_desc, re.IGNORECASE)]

            return NormalizedJob(
                title=title or "Software Engineer",
                company=company,
                location="Remote",
                remote_type="REMOTE",
                employment_type="FULL_TIME",
                description=clean_desc or title,
                job_url=link,
                external_job_id=entry.get("id") or link,
                source_name=self.name,
                skills=skills,
                requirements=skills[:4],
                preferred_skills=skills[4:],
                experience_years_required=_extract_experience_years(clean_desc)
            )
        except Exception as e:
            logger.error(f"Error normalizing RSS job for {self.name}: {e}")
            return None

def get_default_rss_sources() -> List[RSSJobSource]:
    return [
        # NOTE: remoteok.com/remote-jobs.rss now returns HTTP 410 Gone and is
        # intentionally not registered; a permanently dead feed would report
        # a failure on every cycle and pollute source health metrics.
        RSSJobSource(
            name="WeWorkRemotely RSS",
            feed_url="https://weworkremotely.com/categories/remote-programming-jobs.rss"
        ),
    ]
