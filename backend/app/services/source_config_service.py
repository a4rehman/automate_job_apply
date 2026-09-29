"""Ensure JobSourceConfig rows exist for registered sources so DB gating works."""
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging_config import logger
from app.models.job import JobSourceConfig
from app.job_sources import get_all_registered_adapters


async def sync_source_configs(db: AsyncSession) -> List[JobSourceConfig]:
    """Upsert JobSourceConfig rows for every registered adapter.

    New adapters are inserted with defaults (enabled). Existing rows keep their
    enabled/disabled state so an operator's settings survive restarts.
    """
    adapters = get_all_registered_adapters()

    existing_res = await db.execute(select(JobSourceConfig))
    existing = {c.name: c for c in existing_res.scalars().all()}

    for adapter in adapters:
        if adapter.name not in existing:
            cfg = JobSourceConfig(
                name=adapter.name,
                source_type=adapter.source_type,
                url_or_endpoint=getattr(adapter, "feed_url", "") or getattr(adapter, "endpoint", ""),
                is_enabled=True,
                rate_limit_rpm=adapter.rate_limit_rpm,
                requires_auth=adapter.requires_auth,
                supports_auto_submit=adapter.supports_auto_submit,
                requires_user_approval=adapter.requires_user_approval,
            )
            db.add(cfg)
            logger.info(f"Created JobSourceConfig for {adapter.name}")

    await db.commit()

    final_res = await db.execute(select(JobSourceConfig))
    return final_res.scalars().all()