from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.job import SchedulerRun, RunStatus
from app.models.automation import AutomationSettings
from app.schemas.automation import AutomationSettingsResponse, AutomationSettingsUpdate, ManualRunResponse, SchedulerRunResponse
from app.services.automation_pipeline import automation_pipeline
from app.services.audit_service import audit_service
from app.core.config import settings
from app.models.application import Application, ApplicationStatus

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
    dry_run: bool = Query(True, description="Run in dry-run mode (no real submissions)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full automation cycle immediately."""
    result = await automation_pipeline.run_cycle(db=db, user_id=current_user.id, dry_run=dry_run)

    await audit_service.log_event(
        db=db, event_type="MANUAL_RUN_TRIGGERED",
        user_id=current_user.id, entity_type="AUTOMATION",
        details={"result": result, "dry_run": dry_run},
    )

    # run_cycle() nests its counters under "metrics"; reading them from the
    # top level reported 0 for a cycle that had actually done the work.
    metrics = result.get("metrics") or result
    return ManualRunResponse(
        status=result.get("status", RunStatus.FAILED),
        message=result.get("error") or f"Discovered {metrics.get('jobs_discovered', 0)} new jobs, analyzed {metrics.get('jobs_analyzed', 0)} jobs, prepared {metrics.get('applications_prepared', 0)} applications.",
        jobs_discovered=metrics.get("jobs_discovered", 0),
        jobs_analyzed=metrics.get("jobs_analyzed", 0),
        applications_prepared=metrics.get("applications_prepared", 0),
    )


@router.get("/runs", response_model=list[SchedulerRunResponse])
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent automation cycle runs with status."""
    result = await db.execute(
        select(SchedulerRun)
        .order_by(desc(SchedulerRun.started_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/health", response_model=dict)
async def automation_health(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current automation health: latest run, lock state, configured limits."""
    latest = await db.execute(
        select(SchedulerRun)
        .order_by(desc(SchedulerRun.started_at))
        .limit(1)
    )
    latest_run = latest.scalar_one_or_none()

    lock = await db.execute(
        select(SchedulerRun).where(
            SchedulerRun.run_id == "automation_cycle_lock",
            SchedulerRun.status == RunStatus.RUNNING,
        )
    )
    lock_run = lock.scalar_one_or_none()

    result = await db.execute(
        select(AutomationSettings).where(AutomationSettings.user_id == current_user.id)
    )
    settings_row = result.scalar_one_or_none()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    submitted_today = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == current_user.id,
            Application.status.in_([ApplicationStatus.SUBMITTED, ApplicationStatus.APPLIED]),
            Application.created_at >= today_start,
        )
    )
    submitted_count = submitted_today.scalar() or 0

    return {
        "worker_healthy": True,
        "scheduler_enabled": bool(settings_row and settings_row.is_scheduler_enabled),
        "lock_held": bool(lock_run),
        "last_run": {
            "status": latest_run.status if latest_run else None,
            "started_at": latest_run.started_at if latest_run else None,
            "finished_at": latest_run.finished_at if latest_run else None,
            "error": latest_run.error_message if latest_run else None,
            "failures": latest_run.failures if latest_run else 0,
        } if latest_run else None,
        "daily_limit": {
            "used": submitted_count,
            "max": settings.MAX_APPLICATIONS_PER_DAY,
        },
        "dry_run": settings.DRY_RUN,
    }