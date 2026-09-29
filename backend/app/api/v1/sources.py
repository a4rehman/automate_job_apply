from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.job import JobSourceConfig
from app.schemas.job import JobSourceResponse, JobSourceToggle
from app.job_sources import get_all_registered_adapters
from app.services.source_config_service import sync_source_configs
from app.core.logging_config import logger

router = APIRouter(prefix="/sources", tags=["Job Sources"])


@router.get("", response_model=List[JobSourceResponse])
async def list_all_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await sync_source_configs(db)

    adapters = {a.name: a for a in get_all_registered_adapters()}
    cfg_res = await db.execute(select(JobSourceConfig))
    configs = cfg_res.scalars().all()

    result = []
    for cfg in configs:
        adapter = adapters.get(cfg.name)
        result.append(
            JobSourceResponse(
                id=cfg.id,
                name=cfg.name,
                source_type=cfg.source_type,
                url_or_endpoint=cfg.url_or_endpoint
                or (getattr(adapter, "feed_url", "") or getattr(adapter, "endpoint", "") if adapter else ""),
                is_enabled=cfg.is_enabled,
                rate_limit_rpm=cfg.rate_limit_rpm,
                requires_auth=cfg.requires_auth,
                supports_auto_submit=cfg.supports_auto_submit,
                requires_user_approval=cfg.requires_user_approval,
                last_polled_at=cfg.last_polled_at,
                health_status=cfg.health_status,
                consecutive_failures=cfg.consecutive_failures,
            )
        )
    return result


@router.patch("/{source_id}", response_model=JobSourceResponse)
async def toggle_source(
    source_id: int,
    toggle: JobSourceToggle,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg_res = await db.execute(select(JobSourceConfig).where(JobSourceConfig.id == source_id))
    cfg = cfg_res.scalar_one_or_none()
    if not cfg:
        raise HTTPException(status_code=404, detail="Source not found")

    cfg.is_enabled = toggle.is_enabled
    await db.commit()
    await db.refresh(cfg)
    logger.info(f"Source '{cfg.name}' enabled={cfg.is_enabled}")

    return cfg