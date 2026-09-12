from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class SkillBase(BaseModel):
    name: str
    category: str = "TECHNICAL" # LANGUAGES, ML_AI, FRAMEWORKS, CLOUD, TOOLS, SOFT
    proficiency: int = Field(default=4, ge=1, le=5)
    years_experience: float = 1.0
    is_primary: bool = True

class SkillCreate(SkillBase):
    pass

class SkillResponse(SkillBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    current_title: Optional[str] = None
    years_experience: Optional[float] = None
    target_roles: Optional[List[str]] = None
    preferred_industries: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    remote_preference: Optional[str] = "REMOTE"
    salary_min: Optional[float] = None
    salary_currency: Optional[str] = "USD"
    employment_types: Optional[List[str]] = None
    bio: Optional[str] = None

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    phone: str
    city: str
    country: str
    linkedin_url: str
    github_url: str
    portfolio_url: str
    current_title: str
    years_experience: float
    target_roles: List[str]
    preferred_industries: List[str]
    preferred_locations: List[str]
    remote_preference: str
    salary_min: float
    salary_currency: str
    employment_types: List[str]
    bio: str
    skills: List[SkillResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
