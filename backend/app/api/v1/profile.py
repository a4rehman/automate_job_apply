from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.api.deps import get_db, get_current_user
from app.models.user import User, UserProfile
from app.models.resume import Skill
from app.schemas.profile import ProfileResponse, ProfileUpdate, SkillCreate, SkillResponse
from app.services.audit_service import audit_service

router = APIRouter(prefix="/profile", tags=["User Profile"])

@router.get("", response_model=ProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserProfile(user_id=current_user.id, full_name="")
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    skills_res = await db.execute(select(Skill).where(Skill.user_id == current_user.id).order_by(Skill.proficiency.desc()))
    skills = skills_res.scalars().all()

    profile_dict = {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.full_name or "",
        "phone": profile.phone or "",
        "city": profile.city or "",
        "country": profile.country or "",
        "linkedin_url": profile.linkedin_url or "",
        "github_url": profile.github_url or "",
        "portfolio_url": profile.portfolio_url or "",
        "current_title": profile.current_title or "",
        "years_experience": profile.years_experience or 0.0,
        "target_roles": profile.target_roles or [],
        "preferred_industries": profile.preferred_industries or [],
        "preferred_locations": profile.preferred_locations or [],
        "remote_preference": profile.remote_preference or "REMOTE",
        "salary_min": profile.salary_min or 0.0,
        "salary_currency": profile.salary_currency or "USD",
        "employment_types": profile.employment_types or ["FULL_TIME"],
        "bio": profile.bio or "",
        "skills": skills,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }
    return profile_dict

@router.put("", response_model=ProfileResponse)
async def update_user_profile(
    profile_in: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    update_data = profile_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    await audit_service.log_event(
        db=db,
        event_type="PROFILE_UPDATED",
        user_id=current_user.id,
        entity_type="PROFILE",
        entity_id=profile.id
    )

    return await get_user_profile(current_user=current_user, db=db)

@router.post("/skills", response_model=SkillResponse)
async def add_skill(
    skill_in: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if skill name already exists for user
    existing = await db.execute(
        select(Skill).where(Skill.user_id == current_user.id, Skill.name.ilike(skill_in.name))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Skill already exists in profile")

    skill = Skill(
        user_id=current_user.id,
        name=skill_in.name.strip(),
        category=skill_in.category,
        proficiency=skill_in.proficiency,
        years_experience=skill_in.years_experience,
        is_primary=skill_in.is_primary,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)

    return skill

@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Skill).where(Skill.id == skill_id, Skill.user_id == current_user.id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    await db.delete(skill)
    await db.commit()
    return {"message": "Skill deleted successfully", "skill_id": skill_id}
