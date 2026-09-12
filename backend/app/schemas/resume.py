from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ParsedExperience(BaseModel):
    title: str
    company: str
    location: Optional[str] = ""
    start_date: Optional[str] = ""
    end_date: Optional[str] = ""
    description: Optional[str] = ""
    highlights: List[str] = []

class ParsedEducation(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = ""
    graduation_year: Optional[str] = ""

class ParsedResumeData(BaseModel):
    full_name: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    summary: Optional[str] = ""
    skills: List[str] = []
    experience: List[ParsedExperience] = []
    education: List[ParsedEducation] = []
    certifications: List[str] = []
    links: List[str] = []

class ResumeResponse(BaseModel):
    id: int
    user_id: int
    original_filename: str
    file_type: str
    raw_text: str
    parsed_json: Dict[str, Any]
    parsed_summary: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ResumeVersionCreate(BaseModel):
    resume_id: int
    version_name: str
    target_role: str
    tailored_content_json: Dict[str, Any]
    optimized_bullets: List[Dict[str, str]] = []

class ResumeVersionResponse(BaseModel):
    id: int
    resume_id: int
    version_name: str
    target_role: str
    tailored_content_json: Dict[str, Any]
    optimized_bullets: List[Dict[str, str]]
    created_at: datetime

    class Config:
        from_attributes = True

class ResumeOptimizationRequest(BaseModel):
    resume_id: int
    job_id: int

class OptimizedBullet(BaseModel):
    original: str
    optimized: str
    reason: str

class ResumeOptimizationResponse(BaseModel):
    job_id: int
    job_title: str
    company: str
    suggested_headline: str
    optimized_bullets: List[OptimizedBullet]
    keyword_alignment: List[str]
