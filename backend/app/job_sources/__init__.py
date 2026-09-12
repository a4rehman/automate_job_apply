from typing import List, Dict, Type
from app.job_sources.base import JobSource, NormalizedJob
from app.job_sources.rss_feed import RSSJobSource, get_default_rss_sources
from app.job_sources.public_apis import RemotiveAPISource, ArbeitnowAPISource, get_public_api_sources
from app.job_sources.csv_source import CSVJobSource
from app.job_sources.manual_import import ManualJobImporter
from app.job_sources.email_alerts import EmailAlertJobSource
from app.job_sources.adapters.linkedin_adapter import LinkedInAdapter
from app.job_sources.adapters.other_adapters import IndeedAdapter, GlassdoorAdapter, WellfoundAdapter

def get_all_active_sources() -> List[JobSource]:
    sources: List[JobSource] = []
    sources.extend(get_default_rss_sources())
    sources.extend(get_public_api_sources())
    return sources

def get_all_registered_adapters() -> List[JobSource]:
    return [
        *get_default_rss_sources(),
        *get_public_api_sources(),
        LinkedInAdapter(),
        IndeedAdapter(),
        GlassdoorAdapter(),
        WellfoundAdapter(),
        EmailAlertJobSource(),
        CSVJobSource()
    ]

__all__ = [
    "JobSource",
    "NormalizedJob",
    "RSSJobSource",
    "RemotiveAPISource",
    "ArbeitnowAPISource",
    "CSVJobSource",
    "ManualJobImporter",
    "EmailAlertJobSource",
    "LinkedInAdapter",
    "IndeedAdapter",
    "GlassdoorAdapter",
    "WellfoundAdapter",
    "get_all_active_sources",
    "get_all_registered_adapters",
]
