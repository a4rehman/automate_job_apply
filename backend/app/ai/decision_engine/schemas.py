from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class JobDecision(BaseModel):
    """
    Strongly-typed, validated Pydantic model for Gemini structured decision engine.
    All scores are normalized strictly between 0.0 and 1.0.
    """
    role_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fit between target role/title and job title (0.0 to 1.0)"
    )
    skills_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fit between candidate's verified skills and job requirements (0.0 to 1.0)"
    )
    experience_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fit between candidate's experience years and job requirements (0.0 to 1.0)"
    )
    seniority_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Alignment with candidate's seniority level (0.0 to 1.0)"
    )
    semantic_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Deep semantic and domain contextual relevance (0.0 to 1.0)"
    )
    location_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fit with candidate's location and remote preferences (0.0 to 1.0)"
    )
    salary_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Alignment with candidate's salary expectations (0.0 to 1.0)"
    )

    overall_match: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weighted overall match score (0.0 to 1.0)"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model self-reported confidence in evaluation (0.0 to 1.0)"
    )

    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills verified to be present in candidate resume and requested by job"
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required or preferred skills missing from candidate resume"
    )
    concerns: List[str] = Field(
        default_factory=list,
        description="Potential disqualifiers, ambiguities, or flags"
    )

    application_method: Literal[
        "email",
        "authorized_api",
        "manual",
        "unknown"
    ] = Field(
        default="unknown",
        description="Detected method of application"
    )

    decision: Literal[
        "HIGH_MATCH",
        "HUMAN_REVIEW",
        "LOW_MATCH"
    ] = Field(
        default="HUMAN_REVIEW",
        description="Preliminary AI recommendation category"
    )

    requires_human_review: bool = Field(
        default=True,
        description="Whether human approval is required before submission"
    )

    reasoning_summary: str = Field(
        ...,
        min_length=10,
        description="Explainable breakdown justifying the scores and recommendation"
    )

    @field_validator(
        "role_match", "skills_match", "experience_match",
        "seniority_match", "semantic_match", "location_match",
        "salary_match", "overall_match", "confidence",
        mode="before"
    )
    def clamp_scores(cls, v):
        if isinstance(v, (int, float)):
            return max(0.0, min(1.0, float(v)))
        return v


class EmailApplicationExtraction(BaseModel):
    """Structured extraction of email application instructions from job description."""
    is_email_application: bool = Field(
        ...,
        description="True if the job explicitly requests applying via email"
    )
    recipient_email: Optional[str] = Field(
        default=None,
        description="Clean, valid recipient email address extracted from job description"
    )
    email_subject: Optional[str] = Field(
        default=None,
        description="Requested or recommended email subject line"
    )
    required_documents: List[str] = Field(
        default_factory=list,
        description="Documents requested (e.g. CV, Cover Letter, Portfolio, Code Sample)"
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Specific instructions from recruiter regarding email applications"
    )
    contact_name: Optional[str] = Field(
        default=None,
        description="Hiring manager or recruiter name if specified"
    )
    company: Optional[str] = Field(
        default=None,
        description="Target company name"
    )
    role: Optional[str] = Field(
        default=None,
        description="Target job title"
    )


class ApplicationEmailContent(BaseModel):
    """Personalized application email generated from grounded candidate facts."""
    subject: str = Field(..., min_length=5)
    body_text: str = Field(..., min_length=50)
    body_html: str = Field(..., min_length=50)
    highlighted_qualifications: List[str] = Field(default_factory=list)
