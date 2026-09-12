from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.job import JobSourceResponse
from app.job_sources import get_all_registered_adapters

router = APIRouter(prefix="/sources", tags=["Job Sources"])


@router.get("", response_model=List[JobSourceResponse])
async def list_all_sources(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    adapters = get_all_registered_adapters()
    sources = []
    for i, adapter in enumerate(adapters, start=1):
        sources.append(
            JobSourceResponse(
                id=i,
                name=adapter.name,
                source_type=adapter.source_type,
                url_or_endpoint=getattr(adapter, "feed_url", "") or getattr(adapter, "endpoint", ""),
                is_enabled=True,
                rate_limit_rpm=adapter.rate_limit_rpm,
                requires_auth=adapter.requires_auth,
                supports_auto_submit=adapter.supports_auto_submit,
                requires_user_approval=adapter.requires_user_approval,
                last_polled_at=None,
            )
        )
    return sources
