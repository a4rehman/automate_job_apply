from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application, ApplicationAnswer, ApplicationStatus
from app.schemas.application import (
    ApplicationResponse, ApplicationDetailResponse,
    PrepareApplicationRequest, ApplicationAnswerCreate,
    ApplicationAnswerResponse, ApplicationUpdate,
    ApprovalRequest, SubmitRequest,
)
from app.services.application_service import application_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/applications", tags=["Applications"])


def _enrich_response(app: Application, job: Job | None) -> dict:
    d = {
        "id": app.id, "user_id": app.user_id, "job_id": app.job_id,
        "resume_id": app.resume_id, "status": app.status,
        "cover_letter_text": app.cover_letter_text,
        "tailored_resume_bullets": app.tailored_resume_bullets or [],
        "custom_pitch": app.custom_pitch, "screenshot_path": app.screenshot_path,
        "portal_submission_type": app.portal_submission_type,
        "requires_user_approval": app.requires_user_approval,
        "is_user_approved": app.is_user_approved,
        "approved_at": app.approved_at, "applied_at": app.applied_at,
        "interview_date": app.interview_date, "notes": app.notes,
        "salary_offered": app.salary_offered,
        "created_at": app.created_at, "updated_at": app.updated_at,
        "job_title": job.title if job else None,
        "job_company": job.company if job else None,
        "job_url": job.job_url if job else None,
        "job_match_score": job.match_score if job else None,
    }
    return d


@router.get("", response_model=List[ApplicationResponse])
async def list_applications(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Application)
        .where(Application.user_id == current_user.id)
        .order_by(desc(Application.updated_at))
    )
    if status:
        query = query.where(Application.status == status.upper())
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    apps = result.scalars().all()
    responses = []
    for app in apps:
        job_q = await db.execute(select(Job).where(Job.id == app.job_id))
        job = job_q.scalar_one_or_none()
        responses.append(_enrich_response(app, job))
    return responses


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_q = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
    )
    app = app_q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_q.scalar_one_or_none()

    answers_q = await db.execute(
        select(ApplicationAnswer).where(ApplicationAnswer.application_id == app.id)
    )
    answers = answers_q.scalars().all()

    data = _enrich_response(app, job)
    data["answers"] = [ApplicationAnswerResponse.model_validate(a) for a in answers]
    data["job_details"] = {
        "title": job.title, "company": job.company, "description": job.description[:2000],
        "skills": job.skills, "requirements": job.requirements,
        "location": job.location, "remote_type": job.remote_type,
    } if job else None
    return data


@router.post("/prepare", response_model=ApplicationResponse)
@router.post("/prepare/{job_id}", response_model=ApplicationResponse)
async def prepare_application(
    job_id: Optional[int] = None,
    req: Optional[PrepareApplicationRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_job_id = job_id or (req.job_id if req else None)
    if not target_job_id:
        raise HTTPException(status_code=400, detail="job_id is required")
    resume_id = req.resume_id if req else None
    custom_instructions = req.custom_instructions if req else ""

    try:
        app = await application_service.prepare_application(
            db=db, user=current_user, job_id=target_job_id,
            resume_id=resume_id, custom_instructions=custom_instructions or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    job = job_q.scalar_one_or_none()
    return _enrich_response(app, job)


@router.post("/{application_id}/answer", response_model=ApplicationAnswerResponse)
async def generate_answer(
    application_id: int,
    req: ApplicationAnswerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        answer = await application_service.generate_application_answer(
            db=db, application_id=application_id, user=current_user,
            question_text=req.question_text, custom_context=req.custom_context or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return answer


@router.post("/{application_id}/approve", response_model=ApplicationResponse)
async def approve_application(
    application_id: int,
    req: Optional[ApprovalRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_approved = req.approved if req is not None else True
    edited_cover_letter = req.edited_cover_letter if req else None
    notes = req.notes if req else None

    if not is_approved:
        app_q = await db.execute(
            select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
        )
        app = app_q.scalar_one_or_none()
        if app:
            app.status = ApplicationStatus.SAVED
            if notes:
                app.notes = notes
            await db.commit()
            await db.refresh(app)
            job_q = await db.execute(select(Job).where(Job.id == app.job_id))
            return _enrich_response(app, job_q.scalar_one_or_none())
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        app = await application_service.approve_application(
            db=db, application_id=application_id, user=current_user,
            edited_cover_letter=edited_cover_letter, notes=notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    return _enrich_response(app, job_q.scalar_one_or_none())


@router.post("/{application_id}/mark-submitted", response_model=ApplicationResponse)
async def mark_application_submitted(
    application_id: int,
    req: Optional[SubmitRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_q = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
    )
    app = app_q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = ApplicationStatus.APPLIED
    app.applied_at = datetime.now(timezone.utc)
    if req and req.notes:
        app.notes = req.notes

    await db.commit()
    await db.refresh(app)

    await audit_service.log_event(
        db=db,
        event_type="APPLICATION_SUBMITTED_MANUALLY",
        user_id=current_user.id,
        entity_type="APPLICATION",
        entity_id=app.id,
        details={"status": "APPLIED"},
    )

    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    return _enrich_response(app, job_q.scalar_one_or_none())


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_q = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
    )
    app = app_q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    new_status = data.get("status")
    if new_status:
        app.status = getattr(ApplicationStatus, new_status, new_status)
    await db.commit()
    await db.refresh(app)
    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    return _enrich_response(app, job_q.scalar_one_or_none())


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: int,
    update: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_q = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
    )
    app = app_q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(app, field, value)

    await db.commit()
    await db.refresh(app)
    job_q = await db.execute(select(Job).where(Job.id == app.job_id))
    return _enrich_response(app, job_q.scalar_one_or_none())


@router.delete("/{application_id}")
async def delete_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    app_q = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == current_user.id)
    )
    app = app_q.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(app)
    await db.commit()
    return {"message": "Application deleted", "id": application_id}
