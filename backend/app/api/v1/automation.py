from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.automation import AutomationSettings
from app.schemas.automation import AutomationSettingsResponse, AutomationSettingsUpdate, ManualRunResponse
from app.workers.job_monitor_worker import job_monitor_worker
from app.workers.job_analyzer_worker import job_analyzer_worker
from app.services.audit_service import audit_service

router = APIRouter(prefix="/automation", tags=["Automation"])


@router.get("/settings", response_model=AutomationSettingsResponse)
async def get_automation_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationSettings).where(AutomationSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = AutomationSettings(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.put("/settings", response_model=AutomationSettingsResponse)
async def update_automation_settings(
    update: AutomationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AutomationSettings).where(AutomationSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = AutomationSettings(user_id=current_user.id)
        db.add(settings)

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    await db.commit()
    await db.refresh(settings)

    await audit_service.log_event(
        db=db, event_type="AUTOMATION_SETTINGS_UPDATED",
        user_id=current_user.id, entity_type="SETTINGS",
    )
    return settings


@router.post("/run-now", response_model=ManualRunResponse)
async def manual_run(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate job discovery + analysis cycle."""
    monitor_result = await job_monitor_worker.poll_all_sources(db=db)
    analyzed = await job_analyzer_worker.analyze_pending_jobs(db=db)

    await audit_service.log_event(
        db=db, event_type="MANUAL_RUN_TRIGGERED",
        user_id=current_user.id, entity_type="AUTOMATION",
        details=monitor_result,
    )

    return ManualRunResponse(
        status="completed",
        message=f"Discovered {monitor_result['new_jobs_added']} new jobs, analyzed {analyzed} jobs.",
        jobs_discovered=monitor_result["new_jobs_added"],
        jobs_analyzed=analyzed,
        applications_prepared=0,
    )
