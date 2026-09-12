import hashlib
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User, UserProfile
from app.models.job import Job, JobMatch, JobStatus
from app.models.resume import Skill, Resume
from app.schemas.job import (
    JobCreate, JobFilter, JobResponse, JobMatchResponse,
    JobSourceResponse, JobSourceToggle, CSVImportResponse,
)
from app.job_sources.csv_source import CSVJobSource
from app.job_sources.manual_import import ManualJobImporter
from app.job_sources import get_all_registered_adapters
from app.ai.job_analyzer import job_analyzer
from app.services.matching_engine import matching_engine
from app.services.audit_service import audit_service
from app.core.logging_config import logger

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    search: Optional[str] = None,
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    remote_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).order_by(Job.match_score.desc(), Job.detected_date.desc())

    if search:
        term = f"%{search}%"
        query = query.where(or_(Job.title.ilike(term), Job.company.ilike(term)))
    if source:
        query = query.where(Job.source_name == source)
    if min_score is not None:
        query = query.where(Job.match_score >= min_score)
    if remote_type:
        query = query.where(Job.remote_type == remote_type.upper())
    if status:
        query = query.where(Job.status == status)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    responses = []
    for job in jobs:
        match_q = await db.execute(
            select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == current_user.id)
        )
        match = match_q.scalar_one_or_none()
        resp = JobResponse(
            id=job.id,
            title=job.title,
            company=job.company,
            location=job.location,
            remote_type=job.remote_type,
            employment_type=job.employment_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            currency=job.currency,
            description=job.description,
            job_url=job.job_url,
            external_job_id=job.external_job_id,
            source_name=job.source_name,
            source_id=job.source_id,
            requirements=job.requirements or [],
            preferred_skills=job.preferred_skills or [],
            skills=job.skills or [],
            experience_years_required=job.experience_years_required,
            posted_date=job.posted_date,
            detected_date=job.detected_date,
            match_score=job.match_score,
            status=job.status,
            created_at=job.created_at,
            match_details=JobMatchResponse.model_validate(match) if match else None,
        )
        responses.append(resp)
    return responses


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_detail(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    match_q = await db.execute(
        select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == current_user.id)
    )
    match = match_q.scalar_one_or_none()

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        currency=job.currency,
        description=job.description,
        job_url=job.job_url,
        external_job_id=job.external_job_id,
        source_name=job.source_name,
        source_id=job.source_id,
        requirements=job.requirements or [],
        preferred_skills=job.preferred_skills or [],
        skills=job.skills or [],
        experience_years_required=job.experience_years_required,
        posted_date=job.posted_date,
        detected_date=job.detected_date,
        match_score=job.match_score,
        status=job.status,
        created_at=job.created_at,
        match_details=JobMatchResponse.model_validate(match) if match else None,
    )


@router.post("", response_model=JobResponse)
@router.post("/manual", response_model=JobResponse, status_code=201)
async def create_job_manually(
    job_in: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually import a single job posting."""
    normalized = await ManualJobImporter.import_raw_job(
        title=job_in.title,
        company=job_in.company,
        description=job_in.description,
        job_url=job_in.job_url,
        location=job_in.location,
        remote_type=job_in.remote_type,
        salary_min=job_in.salary_min,
        salary_max=job_in.salary_max,
    )

    desc_hash = normalized.description_hash

    # Duplicate check
    dup = await db.execute(
        select(Job).where(
            or_(
                Job.description_hash == desc_hash,
                (Job.job_url != "") & (Job.job_url == normalized.job_url),
            )
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This job already exists in the database")

    job = Job(
        source_name=normalized.source_name,
        external_job_id=normalized.external_job_id or "",
        title=normalized.title,
        company=normalized.company,
        location=normalized.location,
        remote_type=normalized.remote_type,
        employment_type=normalized.employment_type,
        salary_min=normalized.salary_min,
        salary_max=normalized.salary_max,
        currency=normalized.currency,
        description=normalized.description,
        description_hash=desc_hash,
        requirements=normalized.requirements,
        preferred_skills=normalized.preferred_skills,
        skills=normalized.skills,
        experience_years_required=normalized.experience_years_required,
        job_url=normalized.job_url,
        posted_date=normalized.posted_date,
        status=JobStatus.NEW,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await audit_service.log_event(
        db=db,
        event_type="JOB_IMPORTED_MANUALLY",
        user_id=current_user.id,
        entity_type="JOB",
        entity_id=job.id,
        details={"title": job.title, "company": job.company},
    )

    return JobResponse(
        id=job.id, title=job.title, company=job.company,
        location=job.location, remote_type=job.remote_type,
        employment_type=job.employment_type, salary_min=job.salary_min,
        salary_max=job.salary_max, currency=job.currency,
        description=job.description, job_url=job.job_url,
        external_job_id=job.external_job_id, source_name=job.source_name,
        source_id=job.source_id, requirements=job.requirements or [],
        preferred_skills=job.preferred_skills or [],
        skills=job.skills or [],
        experience_years_required=job.experience_years_required,
        posted_date=job.posted_date, detected_date=job.detected_date,
        match_score=job.match_score, status=job.status,
        created_at=job.created_at,
    )


@router.post("/{job_id}/analyze", response_model=JobMatchResponse)
async def analyze_single_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """On-demand AI analysis of a single job against user profile."""
    job_q = await db.execute(select(Job).where(Job.id == job_id))
    job = job_q.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    prof_q = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = prof_q.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not found")

    skills_q = await db.execute(select(Skill).where(Skill.user_id == current_user.id))
    user_skills = [s.name for s in skills_q.scalars().all()]

    res_q = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id, Resume.is_primary == True)
    )
    resume = res_q.scalar_one_or_none()

    # First, run job analysis to extract skills if missing
    if not job.skills and not job.requirements:
        analysis = await job_analyzer.analyze_job_description(job.title, job.company, job.description)
        job.requirements = analysis.get("required_skills", [])
        job.preferred_skills = analysis.get("preferred_skills", [])
        job.skills = analysis.get("skills", [])
        job.experience_years_required = analysis.get("experience_years_required", 2.0)

    match_result = await matching_engine.match_job(
        job=job,
        profile=profile,
        user_skills=user_skills,
        resume_summary=resume.parsed_summary if resume else profile.bio,
    )

    score = match_result["overall_score"]
    job.match_score = score
    if score >= 90:
        job.status = JobStatus.HIGH_MATCH
    elif score >= 75:
        job.status = JobStatus.ANALYZED
    else:
        job.status = JobStatus.LOW_MATCH

    # Upsert JobMatch
    existing_q = await db.execute(
        select(JobMatch).where(JobMatch.job_id == job.id, JobMatch.user_id == current_user.id)
    )
    existing_match = existing_q.scalar_one_or_none()
    if existing_match:
        for key, val in match_result.items():
            setattr(existing_match, key, val)
        existing_match.analyzed_at = datetime.now(timezone.utc)
        job_match = existing_match
    else:
        job_match = JobMatch(
            job_id=job.id,
            user_id=current_user.id,
            analyzed_at=datetime.now(timezone.utc),
            **match_result,
        )
        db.add(job_match)

    await db.commit()
    await db.refresh(job_match)
    return job_match


@router.post("/import-csv", response_model=CSVImportResponse)
async def import_csv_jobs(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = (await file.read()).decode("utf-8", errors="ignore")
    rows = CSVJobSource.parse_csv_content(content)
    csv_source = CSVJobSource()

    new_count = 0
    dup_count = 0
    errors: list[str] = []

    for i, row in enumerate(rows):
        try:
            normalized = await csv_source.normalize_job(row)
            if not normalized:
                errors.append(f"Row {i + 1}: Could not parse")
                continue

            dup = await db.execute(
                select(Job).where(
                    or_(
                        Job.description_hash == normalized.description_hash,
                        (Job.title.ilike(normalized.title)) & (Job.company.ilike(normalized.company)),
                    )
                )
            )
            if dup.scalar_one_or_none():
                dup_count += 1
                continue

            job = Job(
                source_name="CSV Import",
                title=normalized.title,
                company=normalized.company,
                location=normalized.location,
                remote_type=normalized.remote_type,
                employment_type=normalized.employment_type,
                salary_min=normalized.salary_min,
                salary_max=normalized.salary_max,
                currency=normalized.currency,
                description=normalized.description,
                description_hash=normalized.description_hash,
                requirements=normalized.requirements,
                preferred_skills=normalized.preferred_skills,
                skills=normalized.skills,
                experience_years_required=normalized.experience_years_required,
                job_url=normalized.job_url,
                status=JobStatus.NEW,
            )
            db.add(job)
            new_count += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: {str(e)}")

    await db.commit()
    return CSVImportResponse(
        total_parsed=len(rows), new_jobs_added=new_count,
        duplicates_skipped=dup_count, errors=errors,
    )


@router.patch("/{job_id}/status")
async def update_job_status(
    job_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    new_status = data.get("status")
    if new_status:
        job.status = getattr(JobStatus, new_status, new_status)
    await db.commit()
    await db.refresh(job)
    return {"id": job.id, "status": job.status}


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await db.delete(job)
    await db.commit()
    return {"message": "Job deleted", "job_id": job_id}
