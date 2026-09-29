import pytest
from app.ai.decision_engine.schemas import (
    JobDecision,
    EmailApplicationExtraction,
    ApplicationEmailContent,
)
from app.ai.decision_engine.validators import (
    validate_score_bounds,
    validate_email_address,
    sanitize_input_text,
    enforce_deterministic_rule_overrides,
)
from app.ai.decision_engine.confidence import (
    calculate_composite_confidence,
    calculate_resume_evidence_score,
)
from app.ai.decision_engine.gemini_provider import gemini_provider
from app.ai.decision_engine.decision_engine import decision_engine


@pytest.mark.asyncio
async def test_job_decision_schema_validation():
    """Verify JobDecision clamps scores between 0.0 and 1.0."""
    decision = JobDecision(
        role_match=1.5,       # Should be clamped to 1.0
        skills_match=-0.2,    # Should be clamped to 0.0
        experience_match=0.85,
        seniority_match=0.90,
        semantic_match=0.75,
        location_match=1.0,
        salary_match=0.95,
        overall_match=0.88,
        confidence=0.92,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Kubernetes"],
        concerns=[],
        application_method="email",
        decision="HIGH_MATCH",
        requires_human_review=True,
        reasoning_summary="Excellent fit with solid backend background."
    )
    assert decision.role_match == 1.0
    assert decision.skills_match == 0.0
    assert decision.confidence == 0.92
    assert decision.decision == "HIGH_MATCH"


def test_validator_helpers():
    """Test score bounds and input sanitation."""
    assert validate_score_bounds(1.2) == 1.0
    assert validate_score_bounds(-0.5) == 0.0
    assert validate_score_bounds(0.85) == 0.85

    assert validate_email_address("careers@company.com") is True
    assert validate_email_address("invalid-email") is False
    assert validate_email_address("user@localhost") is False

    dirty = "Hello <script>alert(1)</script> World! \x00\x08"
    sanitized = sanitize_input_text(dirty, max_length=50)
    assert "<script>" not in sanitized
    assert "\x00" not in sanitized


def test_rule_overrides():
    """Verify deterministic business rules override LLM recommendations safely."""
    decision = JobDecision(
        role_match=0.9,
        skills_match=0.9,
        experience_match=0.9,
        seniority_match=0.9,
        semantic_match=0.9,
        location_match=1.0,
        salary_match=1.0,
        overall_match=0.92,
        confidence=0.45,  # Low confidence
        matched_skills=["Python", "SQL"],
        missing_skills=["Docker"],
        concerns=[],
        application_method="manual",
        decision="HIGH_MATCH",
        requires_human_review=False,
        reasoning_summary="Great fit for the senior backend position."
    )
    
    # When confidence is below threshold, must flag for human review
    updated = enforce_deterministic_rule_overrides(
        decision=decision,
        min_confidence=0.60,
        high_match_threshold=0.85,
        review_threshold=0.70,
    )
    assert updated.decision == "HUMAN_REVIEW"
    assert updated.requires_human_review is True
    assert any("confidence" in c.lower() for c in updated.concerns)


def test_composite_confidence_calculation():
    """Verify multi-factor composite confidence computation."""
    evidence = calculate_resume_evidence_score(
        matched_skills=["Python", "FastAPI", "Docker"],
        candidate_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        resume_text="Senior backend engineer with 5 years building FastAPI and Docker services in Python."
    )
    assert evidence > 0.70

    conf = calculate_composite_confidence(
        model_confidence=0.85,
        resume_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        job_required_skills=["Python", "FastAPI", "Docker"],
        matched_skills=["Python", "FastAPI", "Docker"],
        semantic_similarity=0.80,
        experience_years_candidate=5.0,
        experience_years_required=3.0,
    )
    assert 0.0 <= conf <= 1.0
    assert conf >= 0.70


@pytest.mark.asyncio
async def test_offline_gemini_provider_evaluation():
    """Verify GeminiProvider deterministic evaluator operates reliably."""
    decision = await gemini_provider.evaluate_job_decision(
        job_title="Senior Python Backend Engineer",
        company="TechCorp Inc",
        job_description="Seeking a Senior Python Backend Engineer with 5+ years experience in FastAPI, Docker, and SQL.",
        job_skills=["Python", "FastAPI", "Docker", "SQL"],
        candidate_name="Alex Mercer",
        target_roles=["Senior Python Backend Engineer", "Backend Engineer"],
        candidate_skills=["Python", "FastAPI", "Docker", "SQL", "PostgreSQL"],
        candidate_experience_years=5.0,
        candidate_bio="Experienced backend developer specializing in Python and distributed systems.",
        candidate_location="Remote",
        candidate_salary_min=120000.0,
    )
    assert decision.overall_match >= 0.80
    assert "Python" in decision.matched_skills
    assert decision.confidence >= 0.70
    assert decision.requires_human_review is True


@pytest.mark.asyncio
async def test_cosine_similarity_computation():
    """Test vector cosine similarity math."""
    vec_a = [1.0, 0.0, 0.5, 0.5]
    vec_b = [1.0, 0.0, 0.5, 0.5]
    sim = gemini_provider.calculate_cosine_similarity(vec_a, vec_b)
    assert pytest.approx(sim, 0.01) == 1.0

    vec_c = [0.0, 1.0, 0.0, 0.0]
    sim_orthogonal = gemini_provider.calculate_cosine_similarity(vec_a, vec_c)
    assert pytest.approx(sim_orthogonal, 0.01) == 0.0
