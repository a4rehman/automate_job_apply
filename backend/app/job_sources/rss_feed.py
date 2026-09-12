import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import feedparser
import httpx
from app.job_sources.base import JobSource, NormalizedJob
from app.core.logging_config import logger

class RSSJobSource(JobSource):
    def __init__(self, name: str, feed_url: str):
        super().__init__(name=name, source_type="RSS")
        self.feed_url = feed_url

    async def fetch_jobs(self, limit: int = 30) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(self.feed_url, headers={"User-Agent": "Mozilla/5.0 (AI Job Agent)"})
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch RSS {self.name}: HTTP {response.status_code}")
                    return []
                feed = feedparser.parse(response.text)
                return feed.entries[:limit]
        except Exception as e:
            logger.error(f"Error reading RSS feed {self.name}: {e}")
            return []

    async def normalize_job(self, entry: Dict[str, Any]) -> Optional[NormalizedJob]:
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", "") or entry.get("description", "")
            
            # Clean HTML tags
            clean_desc = re.sub(r'<[^>]+>', ' ', summary)
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            
            # Extract company if in title e.g. "Company: Title" or "Title at Company"
            company = "Remote Tech Co"
            if " at " in title:
                parts = title.split(" at ")
                title = parts[0].strip()
                company = parts[1].strip()
            elif ":" in title:
                parts = title.split(":")
                company = parts[0].strip()
                title = parts[1].strip()

            # Extract basic skills from description
            tech_keywords = [
                "Python", "FastAPI", "Machine Learning", "Deep Learning", "LLM",
                "LangChain", "OpenAI", "PyTorch", "TensorFlow", "Pandas", "SQL",
                "Docker", "Kubernetes", "AWS", "RAG", "Vector Databases", "TypeScript", "React"
            ]
            skills = [kw for kw in tech_keywords if re.search(rf'\b{re.escape(kw)}\b', clean_desc, re.IGNORECASE)]

            return NormalizedJob(
                title=title or "Software Engineer",
                company=company or "Remote Company",
                location="Remote",
                remote_type="REMOTE",
                employment_type="FULL_TIME",
                description=clean_desc or title,
                job_url=link,
                external_job_id=entry.get("id", link),
                source_name=self.name,
                skills=skills,
                requirements=skills[:4],
                preferred_skills=skills[4:],
                experience_years_required=2.0
            )
        except Exception as e:
            logger.error(f"Error normalizing RSS job for {self.name}: {e}")
            return None

def get_default_rss_sources() -> List[RSSJobSource]:
    return [
        RSSJobSource(
            name="RemoteOK RSS",
            feed_url="https://remoteok.com/remote-jobs.rss"
        ),
        RSSJobSource(
            name="WeWorkRemotely RSS",
            feed_url="https://weworkremotely.com/categories/remote-programming-jobs.rss"
        )
    ]
