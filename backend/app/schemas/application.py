from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ApplicationAnswerBase(BaseModel):
    question_text: str
    generated_answer: str
    user_edited_answer: Optional[str] = None
    category: str = "MOTIVATION"

class ApplicationAnswerCreate(BaseModel):
    question_text: str
    custom_context: Optional[str] = None

class ApplicationAnswerResponse(ApplicationAnswerBase):
    id: int
    application_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ApplicationCreate(BaseModel):
    job_id: int
    resume_id: Optional[int] = None
    notes: Optional[str] = ""

class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    cover_letter_text: Optional[str] = None
    custom_pitch: Optional[str] = None
    notes: Optional[str] = None
    interview_date: Optional[datetime] = None
    salary_offered: Optional[float] = None
    is_user_approved: Optional[bool] = None

class ApplicationResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    resume_id: Optional[int] = None
    status: str
    cover_letter_text: str
    tailored_resume_bullets: List[Dict[str, Any]] = []
    custom_pitch: str
    screenshot_path: str
    portal_submission_type: str
    requires_user_approval: bool
    is_user_approved: bool
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    interview_date: Optional[datetime] = None
    notes: str
    salary_offered: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    # Nested job summary
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    job_url: Optional[str] = None
    job_match_score: Optional[float] = None

    class Config:
        from_attributes = True

class ApplicationDetailResponse(ApplicationResponse):
    answers: List[ApplicationAnswerResponse] = []
    job_details: Optional[Dict[str, Any]] = None

class PrepareApplicationRequest(BaseModel):
    job_id: int
    resume_id: Optional[int] = None
    custom_instructions: Optional[str] = None

class ApprovalRequest(BaseModel):
    application_id: int
    approved: bool
    edited_cover_letter: Optional[str] = None
    notes: Optional[str] = None

class SubmitRequest(BaseModel):
    application_id: Optional[int] = None
    submission_method: str = "MANUAL_APPROVED" # MANUAL_APPROVED, PLAYWRIGHT_ASSISTED
    notes: Optional[str] = ""
