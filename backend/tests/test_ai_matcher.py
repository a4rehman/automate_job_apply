import pytest
from app.services.resume_parser import ResumeParserService
from app.services.matching_engine import MatchingEngineService


@pytest.mark.asyncio
async def test_resume_parser_fallback():
    sample_text = """
    Alex Mercer
    Email: alex.mercer@example.com | Phone: 555-019-2834
    LinkedIn: linkedin.com/in/alexmercer | GitHub: github.com/alexmercer

    Professional Summary:
    Experienced AI Engineer with 6+ years in deep learning, LLM fine-tuning, RAG architectures, and scalable Python backend development.

    Skills:
    Python, PyTorch, TensorFlow, FastAPI, Docker, Kubernetes, LangChain, PostgreSQL, Redis, AWS, Git

    Experience:
    Senior AI Engineer - NovaTech Systems (2022 - Present)
    - Architected enterprise RAG system reducing support latency by 65%.
    - Deployed multi-agent systems serving 1M+ daily queries using FastAPI and Redis.

    Education:
    B.S. in Computer Science - University of California, Berkeley (2018)
    """

    parsed = ResumeParserService._fallback_regex_parser(sample_text)
    assert parsed is not None
    assert parsed.email == "alex.mercer@example.com"
    skills_lower = [s.lower() for s in parsed.skills]
    assert any("python" in s for s in skills_lower)
    assert any("docker" in s for s in skills_lower)


@pytest.mark.asyncio
async def test_matching_engine_skills_scoring():
    user_skills = ["Python", "PyTorch", "FastAPI", "Docker", "PostgreSQL", "LangChain", "Redis"]
    job_skills = ["Python", "PyTorch", "FastAPI", "Docker", "Kubernetes", "AWS"]

    score, matching, missing = MatchingEngineService.calculate_skills_score(
        user_skills=user_skills,
        job_skills=job_skills,
        required_skills=job_skills,
    )

    assert 0 <= score <= 100
    assert score >= 60  # 4 out of 6 matching = 66.67%
    assert len(matching) == 4
    assert "Kubernetes" in missing
    assert "AWS" in missing
