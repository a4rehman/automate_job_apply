import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.models.user import User, UserProfile
from app.models.job import Job, JobMatch, JobStatus
from app.models.application import (
    Application,
    ApplicationStatus,
    ApplicationPackage,
)
from app.models.notification import OutboundEmail
from app.ai.decision_engine.gemini_provider import gemini_provider
from app.services.application_executor import application_executor


@pytest.mark.asyncio
async def test_email_application_detection():
    """Verify that email application instructions and addresses are accurately parsed."""
    jd = (
        "We are hiring a Lead Python Developer! "
        "Interested candidates should email their resume and portfolio to careers@innovatetech.io "
        "with the subject line 'Lead Python Developer Application'."
    )
    extraction = await gemini_provider.extract_email_application(
        job_description=jd,
        company="InnovateTech",
        role="Lead Python Developer",
    )
    assert extraction.is_email_application is True
    assert extraction.recipient_email == "careers@innovatetech.io"
    assert "InnovateTech" in extraction.company


@pytest.mark.asyncio
async def test_email_generation_strict_grounding():
    """Verify generated email contains grounded facts and valid formatting."""
    email_content = await gemini_provider.generate_application_email(
        candidate_name="Jane Doe",
        candidate_email="jane.doe@example.com",
        candidate_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        candidate_bio="Experienced software engineer with 6 years building distributed APIs.",
        company="TechCorp",
        role="Senior Backend Engineer",
        recipient_name="Hiring Team",
    )
    assert "Jane Doe" in email_content.body_text
    assert "Senior Backend Engineer" in email_content.subject
    assert "Python" in email_content.body_text
    assert email_content.body_html.startswith("<p>")


@pytest.mark.asyncio
async def test_email_application_execution_and_outbound_tracking(db_session: AsyncSession, test_user: User):
    """Test full email application execution lifecycle with OutboundEmail creation."""
    # Create test job
    job = Job(
        source_name="TEST_FEED",
        title="Python Specialist",
        company="Global Software Inc",
        location="Remote",
        remote_type="REMOTE",
        description="Please send your CV to hiring@globalsoft.com",
        description_hash="testhash_globalsoft_123",
        skills=["Python", "SQL"],
        job_url="https://globalsoft.com/jobs/123",
        status=JobStatus.ANALYZED,
    )
    db_session.add(job)
    await db_session.flush()

    # Create application with review
    app = Application(
        user_id=test_user.id,
        job_id=job.id,
        status=ApplicationStatus.APPROVED,
        application_method="email",
    )
    db_session.add(app)
    await db_session.flush()

    package = ApplicationPackage(
        application_id=app.id,
        email_subject="Application for Python Specialist",
        email_body_text="Dear Hiring Team, Please accept my application for Python Specialist.",
        recipient_email="hiring@globalsoft.com",
    )
    db_session.add(package)
    await db_session.commit()

    # Execute application in DRY RUN mode
    result = await application_executor.submit(
        db=db_session,
        user=test_user,
        job=job,
        application=app,
        dry_run=True,
    )

    assert result["success"] is True

    # Verify OutboundEmail was created
    stmt = select(OutboundEmail).where(OutboundEmail.application_id == app.id)
    outbound = (await db_session.execute(stmt)).scalar_one_or_none()
    assert outbound is not None
    assert outbound.recipient_email == "hiring@globalsoft.com"
    assert "DRY_RUN" in outbound.status

    # Verify idempotency: running again should not duplicate
    re_result = await application_executor.submit(
        db=db_session,
        user=test_user,
        job=job,
        application=app,
        dry_run=True,
    )
    assert re_result["success"] is False
    assert "terminal" in re_result.get("message", "").lower() or "lock" in re_result.get("message", "").lower()


@pytest.mark.asyncio
async def test_dry_run_duplicate_leaves_no_orphan_attempt(db_session: AsyncSession, test_user: User):
    """A retried dry run must not leak an IN_PROGRESS ExecutionAttempt.

    Regression: the idempotency check used to run *after* the attempt row was
    created and committed, so every retried cycle permanently left a dangling
    IN_PROGRESS attempt that never completed, inflating the audit trail.
    """
    from app.models.application import ExecutionAttempt
    from app.services.application_executor import EmailApplicationExecutor
    from app.models.user import UserProfile

    job = Job(
        source_name="TEST_FEED",
        title="Backend Engineer",
        company="Orphan Co",
        location="Remote",
        remote_type="REMOTE",
        description="Apply by emailing careers@orphanco.com",
        description_hash="testhash_orphan_001",
        skills=["Python"],
        job_url="https://orphanco.com/jobs/1",
        status=JobStatus.ANALYZED,
    )
    db_session.add(job)
    await db_session.flush()

    app = Application(
        user_id=test_user.id,
        job_id=job.id,
        status=ApplicationStatus.APPROVED,
        application_method="email",
    )
    db_session.add(app)
    await db_session.commit()

    profile = (await db_session.execute(
        select(UserProfile).where(UserProfile.user_id == test_user.id)
    )).scalar_one()

    args = dict(
        db=db_session, user=test_user, job=job, application=app,
        profile=profile, user_skills=["Python"], dry_run=True,
    )
    first = await EmailApplicationExecutor.execute(**args)
    assert first["success"] is True
    assert first["status"] == "WOULD_SEND_EMAIL"

    # Simulate the worker retrying the same application.
    second = await EmailApplicationExecutor.execute(**args)
    assert second["success"] is False
    assert second["status"] == "DUPLICATE_SKIPPED"

    attempts = (await db_session.execute(
        select(ExecutionAttempt).where(ExecutionAttempt.application_id == app.id)
    )).scalars().all()

    # Exactly one attempt, and it must be finished -- no dangling IN_PROGRESS.
    assert len(attempts) == 1, f"expected 1 attempt, got {len(attempts)}"
    assert attempts[0].status == "SUCCESS"
    assert attempts[0].completed_at is not None

    # And only one audit email was ever recorded.
    emails = (await db_session.execute(
        select(OutboundEmail).where(OutboundEmail.application_id == app.id)
    )).scalars().all()
    assert len(emails) == 1
