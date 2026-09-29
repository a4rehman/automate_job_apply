import sys
import unittest
import asyncio

# Test 1: Gemini Decision Engine schemas & validation
from app.ai.decision_engine.schemas import JobDecision, EmailApplicationExtraction, ApplicationEmailContent
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
from app.core.security import verify_password, get_password_hash


class TestJobAgentSuite(unittest.TestCase):
    def test_job_decision_schema(self):
        decision = JobDecision(
            role_match=1.5,
            skills_match=-0.2,
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
        self.assertEqual(decision.role_match, 1.0)
        self.assertEqual(decision.skills_match, 0.0)
        self.assertEqual(decision.confidence, 0.92)
        self.assertEqual(decision.decision, "HIGH_MATCH")

    def test_validators(self):
        self.assertEqual(validate_score_bounds(1.5), 1.0)
        self.assertEqual(validate_score_bounds(-0.5), 0.0)
        self.assertEqual(validate_score_bounds(0.85), 0.85)

        self.assertTrue(validate_email_address("careers@innovatetech.io"))
        self.assertFalse(validate_email_address("invalid-email"))
        self.assertFalse(validate_email_address("user@localhost"))

        sanitized = sanitize_input_text("Hello <script>alert(1)</script> World! \x00", 50)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("\x00", sanitized)

    def test_rule_overrides(self):
        decision = JobDecision(
            role_match=0.9,
            skills_match=0.9,
            experience_match=0.9,
            seniority_match=0.9,
            semantic_match=0.9,
            location_match=1.0,
            salary_match=1.0,
            overall_match=0.92,
            confidence=0.45,
            matched_skills=["Python", "SQL"],
            missing_skills=["Docker"],
            concerns=[],
            application_method="manual",
            decision="HIGH_MATCH",
            requires_human_review=False,
            reasoning_summary="Great fit for the senior engineer position."
        )
        updated = enforce_deterministic_rule_overrides(
            decision=decision,
            min_confidence=0.60,
            high_match_threshold=0.85,
            review_threshold=0.70,
        )
        self.assertEqual(updated.decision, "HUMAN_REVIEW")
        self.assertTrue(updated.requires_human_review)

    def test_composite_confidence(self):
        evidence = calculate_resume_evidence_score(
            matched_skills=["Python", "FastAPI", "Docker"],
            candidate_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
            resume_text="Senior backend engineer with 5 years building FastAPI and Docker services in Python."
        )
        self.assertGreater(evidence, 0.70)
        conf = calculate_composite_confidence(
            model_confidence=0.85,
            resume_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
            job_required_skills=["Python", "FastAPI", "Docker"],
            matched_skills=["Python", "FastAPI", "Docker"],
            semantic_similarity=0.80,
            experience_years_candidate=5.0,
            experience_years_required=3.0,
        )
        self.assertTrue(0.0 <= conf <= 1.0)
        self.assertGreaterEqual(conf, 0.70)

    def test_auth_gate_and_bcrypt(self):
        raw = "MySecretAdminPass2026!"
        hashed = get_password_hash(raw)
        self.assertTrue(verify_password(raw, hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_async_gemini_and_email(self):
        async def run_async():
            # Test Gemini offline evaluator
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
            self.assertGreaterEqual(decision.overall_match, 0.80)
            self.assertIn("Python", decision.matched_skills)

            # Test email extraction
            extraction = await gemini_provider.extract_email_application(
                job_description="Send CV and cover letter to jobs@ai-startup.io for immediate review.",
                company="AI Startup",
                role="AI Engineer",
            )
            self.assertTrue(extraction.is_email_application)
            self.assertEqual(extraction.recipient_email, "jobs@ai-startup.io")

            # Test grounded email generation
            email_content = await gemini_provider.generate_application_email(
                candidate_name="Alex Mercer",
                candidate_email="alex@example.com",
                candidate_skills=["Python", "FastAPI", "Docker"],
                candidate_bio="AI engineer with 5 years experience.",
                company="AI Startup",
                role="AI Engineer",
            )
            self.assertIn("Alex Mercer", email_content.body_text)
            self.assertIn("AI Engineer", email_content.subject)

        asyncio.run(run_async())

    def test_database_and_email_executor(self):
        async def run_db_test():
            from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import select
            from app.core.database import Base
            from app.models.user import User, UserProfile
            from app.models.job import Job, JobStatus
            from app.models.application import Application, ApplicationStatus, ApplicationPackage
            from app.models.notification import OutboundEmail
            from app.services.application_executor import application_executor

            engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with TestSession() as session:
                user = User(email="test@jobagent.ai", hashed_password="hashedpassword123", is_active=True)
                session.add(user)
                await session.flush()

                job = Job(
                    source_name="TEST_FEED",
                    title="Senior Python Engineer",
                    company="Innovate Solutions",
                    location="Remote",
                    remote_type="REMOTE",
                    description="Send applications to jobs@innovatesolutions.com",
                    description_hash="testhash_innovate_123",
                    skills=["Python", "FastAPI", "Docker"],
                    job_url="https://innovatesolutions.com/job/1",
                    status=JobStatus.ANALYZED,
                )
                session.add(job)
                await session.flush()

                app = Application(
                    user_id=user.id,
                    job_id=job.id,
                    status=ApplicationStatus.APPROVED,
                    application_method="email",
                )
                session.add(app)
                await session.flush()

                package = ApplicationPackage(
                    application_id=app.id,
                    email_subject="Application for Senior Python Engineer",
                    email_body_text="Dear Team, please review my application.",
                    recipient_email="jobs@innovatesolutions.com",
                )
                session.add(package)
                await session.commit()

                # Execute application in dry-run mode
                exec_result = await application_executor.submit(
                    db=session,
                    user=user,
                    job=job,
                    application=app,
                    dry_run=True,
                )
                self.assertTrue(exec_result["success"])

                # Verify OutboundEmail was created
                stmt = select(OutboundEmail).where(OutboundEmail.application_id == app.id)
                outbound = (await session.execute(stmt)).scalar_one_or_none()
                self.assertIsNotNone(outbound)
                self.assertEqual(outbound.recipient_email, "jobs@innovatesolutions.com")
                self.assertIn("DRY_RUN", outbound.status)

            await engine.dispose()

        asyncio.run(run_db_test())


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJobAgentSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
