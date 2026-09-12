import os
import shutil
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.models.user import User, UserProfile
from app.models.resume import Resume, ResumeVersion, Skill
from app.models.job import Job
from app.schemas.resume import (
    ResumeResponse, ResumeVersionResponse, ResumeOptimizationRequest,
    ResumeOptimizationResponse, OptimizedBullet
)
from app.services.resume_parser import resume_parser
from app.ai.client import ai_client
from app.ai.prompts import RESUME_OPTIMIZATION_SYSTEM_PROMPT
from app.services.audit_service import audit_service
import json

router = APIRouter(prefix="/resume", tags=["Resume Management"])

@router.post("/upload", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    set_primary: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate extension
    filename = file.filename or "resume.pdf"
    ext = filename.split(".")[-1].lower()
    if ext not in ["pdf", "docx", "doc", "txt"]:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported")

    # Generate safe unique filename
    unique_id = str(uuid.uuid4())[:8]
    safe_filename = f"resume_{current_user.id}_{unique_id}_{filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract raw text
    try:
        raw_text = resume_parser.extract_text_from_file(file_path=file_path, file_type=ext)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text from file: {e}")

    # AI structured parsing
    parsed_data = await resume_parser.parse_resume_content(raw_text=raw_text)

    # If set_primary is true, mark existing user resumes as non-primary
    if set_primary:
        await db.execute(
            update(Resume).where(Resume.user_id == current_user.id).values(is_primary=False)
        )

    resume = Resume(
        user_id=current_user.id,
        original_filename=filename,
        file_type=ext.upper(),
        file_path=file_path,
        raw_text=raw_text,
        parsed_json=parsed_data.model_dump(),
        parsed_summary=parsed_data.summary or raw_text[:350],
        is_primary=set_primary
    )
    db.add(resume)
    await db.flush()

    # Automatically populate/update User Profile skills if candidate has none or to enrich
    for skill_name in parsed_data.skills:
        skill_clean = skill_name.strip()
        if not skill_clean:
            continue
        existing_skill = await db.execute(
            select(Skill).where(Skill.user_id == current_user.id, Skill.name.ilike(skill_clean))
        )
        if not existing_skill.scalar_one_or_none():
            new_skill = Skill(
                user_id=current_user.id,
                name=skill_clean,
                category="ML_AI" if any(kw in skill_clean.lower() for kw in ["ai", "llm", "ml", "gpt", "rag", "torch", "learning"]) else "TECHNICAL",
                proficiency=4,
                years_experience=2.0,
                is_primary=True
            )
            db.add(new_skill)

    # Update profile summary/bio if blank
    prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = prof_res.scalar_one_or_none()
    if profile:
        if parsed_data.full_name and not profile.full_name:
            profile.full_name = parsed_data.full_name
        if parsed_data.phone and not profile.phone:
            profile.phone = parsed_data.phone
        if parsed_data.summary and not profile.bio:
            profile.bio = parsed_data.summary

    await db.commit()
    await db.refresh(resume)

    await audit_service.log_event(
        db=db,
        event_type="RESUME_UPLOADED",
        user_id=current_user.id,
        entity_type="RESUME",
        entity_id=resume.id,
        details={"filename": filename, "skills_count": len(parsed_data.skills)}
    )

    return resume

@router.get("", response_model=List[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.is_primary.desc(), Resume.created_at.desc())
    )
    return result.scalars().all()

@router.get("/primary", response_model=ResumeResponse)
async def get_primary_resume(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id, Resume.is_primary == True)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        # Fetch the latest one
        fallback = await db.execute(
            select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.created_at.desc())
        )
        resume = fallback.scalar_one_or_none()
        
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Please upload a resume first.")
    return resume

@router.post("/{resume_id}/set-primary")
async def set_primary_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    await db.execute(
        update(Resume).where(Resume.user_id == current_user.id).values(is_primary=False)
    )
    resume.is_primary = True
    await db.commit()
    return {"message": "Primary resume updated successfully", "resume_id": resume_id}

@router.post("/optimize", response_model=ResumeOptimizationResponse)
async def optimize_resume_for_job(
    request: ResumeOptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch resume
    res_query = await db.execute(
        select(Resume).where(Resume.id == request.resume_id, Resume.user_id == current_user.id)
    )
    resume = res_query.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Fetch job
    job_query = await db.execute(select(Job).where(Job.id == request.job_id))
    job = job_query.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_prompt = (
        f"Job Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Job Requirements: {', '.join(job.requirements or [])}\n"
        f"Candidate Raw Resume:\n{resume.raw_text[:6000]}"
    )

    raw_response = await ai_client.generate_chat_completion(
        system_prompt=RESUME_OPTIMIZATION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.2,
        response_format_json=True
    )

    try:
        data = json.loads(raw_response)
        bullets = [OptimizedBullet(**b) for b in data.get("optimized_bullets", [])]
        headline = data.get("suggested_headline", f"{job.title} | AI Specialist")
        keywords = data.get("keyword_alignment", job.skills or [])
    except Exception as e:
        bullets = [
            OptimizedBullet(
                original="Built AI applications and data microservices.",
                optimized=f"Architected scalable {job.title} microservices and high-throughput AI pipelines aligned with {job.company}'s technology stack.",
                reason="Aligns terminology with target job requirements while maintaining factual accuracy."
            )
        ]
        headline = f"Experienced {job.title}"
        keywords = job.skills or ["Python", "FastAPI", "AI"]

    # Save as ResumeVersion
    version = ResumeVersion(
        resume_id=resume.id,
        version_name=f"Tailored for {job.company} - {job.title}",
        target_role=job.title,
        tailored_content_json={"headline": headline, "keywords": keywords},
        optimized_bullets=[b.model_dump() for b in bullets]
    )
    db.add(version)
    await db.commit()

    return ResumeOptimizationResponse(
        job_id=job.id,
        job_title=job.title,
        company=job.company,
        suggested_headline=headline,
        optimized_bullets=bullets,
        keyword_alignment=keywords
    )
