from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.job import Job, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.audit import AuditLog
from app.schemas.analytics import (
    DashboardStatsResponse, AnalyticsSummaryResponse,
    MatchDistributionItem, ApplicationFunnelItem,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=AnalyticsSummaryResponse)
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Jobs found today
    jobs_today = await db.execute(
        select(func.count(Job.id)).where(Job.detected_date >= today_start)
    )
    jobs_found_today = jobs_today.scalar() or 0

    # High-match jobs
    high_match = await db.execute(
        select(func.count(Job.id)).where(Job.match_score >= 90.0)
    )
    high_match_count = high_match.scalar() or 0

    # Application counts
    prepared = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == current_user.id,
            Application.status.in_([
                ApplicationStatus.PREPARING,
                ApplicationStatus.PENDING_APPROVAL,
            ]),
        )
    )
    prepared_count = prepared.scalar() or 0

    applied = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == current_user.id,
            Application.status == ApplicationStatus.APPLIED,
        )
    )
    applied_count = applied.scalar() or 0

    interview = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == current_user.id,
            Application.status == ApplicationStatus.INTERVIEW,
        )
    )
    interview_count = interview.scalar() or 0

    total_applied_ever = await db.execute(
        select(func.count(Application.id)).where(
            Application.user_id == current_user.id,
            Application.status.in_([
                ApplicationStatus.APPLIED,
                ApplicationStatus.INTERVIEW,
                ApplicationStatus.OFFER,
                ApplicationStatus.REJECTED,
            ]),
        )
    )
    total_applied = total_applied_ever.scalar() or 0
    interview_rate = round((interview_count / total_applied * 100), 1) if total_applied > 0 else 0.0

    total_jobs = await db.execute(select(func.count(Job.id)))
    total_jobs_count = total_jobs.scalar() or 0

    avg_score_q = await db.execute(select(func.avg(Job.match_score)).where(Job.match_score > 0))
    avg_score = round(avg_score_q.scalar() or 0.0, 1)

    stats = DashboardStatsResponse(
        jobs_found_today=jobs_found_today,
        high_match_jobs_count=high_match_count,
        applications_prepared_count=prepared_count,
        applications_applied_count=applied_count,
        interview_count=interview_count,
        interview_rate_percentage=interview_rate,
        total_jobs_tracked=total_jobs_count,
        avg_match_score=avg_score,
    )

    # Match distribution
    ranges = [
        ("90-100%", 90, 101), ("75-89%", 75, 90),
        ("50-74%", 50, 75), ("0-49%", 0, 50),
    ]
    match_dist = []
    for label, lo, hi in ranges:
        cnt_q = await db.execute(
            select(func.count(Job.id)).where(
                and_(Job.match_score >= lo, Job.match_score < hi)
            )
        )
        match_dist.append(MatchDistributionItem(range_label=label, count=cnt_q.scalar() or 0))

    # Application funnel
    funnel_statuses = [
        (ApplicationStatus.SAVED, "Saved"),
        (ApplicationStatus.PREPARING, "Preparing"),
        (ApplicationStatus.PENDING_APPROVAL, "Pending Approval"),
        (ApplicationStatus.APPLIED, "Applied"),
        (ApplicationStatus.INTERVIEW, "Interview"),
        (ApplicationStatus.OFFER, "Offer"),
        (ApplicationStatus.REJECTED, "Rejected"),
    ]
    funnel = []
    for st, label in funnel_statuses:
        cnt_q = await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == current_user.id, Application.status == st
            )
        )
        funnel.append(ApplicationFunnelItem(status=st, label=label, count=cnt_q.scalar() or 0))

    # Recent audit logs
    recent_q = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(15)
    )
    recent = [
        {"event_type": a.event_type, "entity_type": a.entity_type,
         "entity_id": a.entity_id, "timestamp": str(a.timestamp)}
        for a in recent_q.scalars().all()
    ]

    return AnalyticsSummaryResponse(
        stats=stats, match_distribution=match_dist,
        application_funnel=funnel, recent_activity=recent,
    )


@router.get("/kpis")
async def get_kpis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await get_dashboard_analytics(current_user, db)
    return {
        "total_jobs_tracked": summary.stats.total_jobs_tracked,
        "jobs_added_today": summary.stats.jobs_found_today,
        "high_matches_count": summary.stats.high_match_jobs_count,
        "ready_for_review_count": summary.stats.applications_prepared_count,
        "applications_submitted": summary.stats.applications_applied_count,
        "interviews_scheduled": summary.stats.interview_count,
        "average_match_score": summary.stats.avg_match_score,
    }


@router.get("/funnel")
async def get_funnel_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await get_dashboard_analytics(current_user, db)
    return {
        "discovered": summary.stats.total_jobs_tracked,
        "match_filtered": summary.stats.high_match_jobs_count,
        "prepared": summary.stats.applications_prepared_count,
        "approved": summary.stats.applications_applied_count + summary.stats.interview_count,
        "submitted": summary.stats.applications_applied_count,
    }


@router.get("/match-distribution")
async def get_match_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    summary = await get_dashboard_analytics(current_user, db)
    return summary.match_distribution
