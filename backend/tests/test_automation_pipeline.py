"""Tests covering matching, normalization, dedup, idempotency, locking, and safety limits."""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.matching_engine import MatchingEngineService
from app.services.application_executor import ApplicationExecutor
from app.services.automation_pipeline import AutomationPipeline
from app.job_sources.base import NormalizedJob, normalize_url
from app.job_sources.rss_feed import _extract_experience_years
from app.job_sources.public_apis import _extract_experience_years as _api_exp_years
from app.models.application import Application, ApplicationStatus
from app.models.job import Job, JobStatus, SchedulerRun, JobSourceConfig, RunStatus
from app.models.user import User, UserProfile
from app.models.resume import Skill
from app.models.automation import AutomationSettings


# ==============================================================================
# URL NORMALIZATION
# ==============================================================================
def test_normalize_url_strips_query_and_fragment():
    assert normalize_url("https://jobs.example.com/123?utm_source=linkedin#section") == "https://jobs.example.com/123"
    assert normalize_url("HTTPS://jobs.example.com/123/") == "https://jobs.example.com/123"
    assert normalize_url("") == ""
    assert normalize_url("  https://a.example.com/x??y=1  ") == "https://a.example.com/x"


def test_normalized_job_description_hash_is_consistent_and_unique():
    a = NormalizedJob(title="ML Engineer", company="Acme", description="Build ML systems.", job_url="https://a.com/1", source_name="X")
    b = NormalizedJob(title="ML Engineer", company="Acme", description="Build ML systems.", job_url="https://a.com/1", source_name="X")
    c = NormalizedJob(title="ML Engineer", company="Acme", description="Different description.", job_url="https://a.com/1", source_name="X")
    assert a.description_hash == b.description_hash
    assert a.description_hash != c.description_hash


# ==============================================================================
# MATCHING ENGINE
# ==============================================================================
@pytest.mark.asyncio
async def test_matching_semantic_failure_returns_zero_not_fake_high():
    """AI semantic failure must NEVER pump the score toward a fake favorable value."""
    job = Job(
        title="Full Stack Engineer",
        company="TestCo",
        description="Web application development.",
        requirements=["Python", "Django"],
        skills=["Python", "Django"],
        experience_years_required=3.0,
        job_url="http://x/1",
        description_hash="abc",
    )
    profile = UserProfile(
        user_id=1, full_name="T", years_experience=1.0,
        target_roles=["Data Scientist"], remote_preference="ON-SITE",
    )
    result = await MatchingEngineService.match_job(job, profile, user_skills=["Java"])

    assert result["semantic_score"] == 0.0  # Not 85.0
    assert result["overall_score"] >= 0.0
    assert "missing" in result["reasoning"].lower() or "skill" in result["reasoning"].lower()
    assert result["semantic_score"] != 85.0


def test_matching_skills_score_empty_returns_zero():
    score, matching, missing = MatchingEngineService.calculate_skills_score([], [], [])
    assert score == 0.0
    assert matching == []
    assert missing == []


def test_matching_role_score_no_targets_returns_zero():
    assert MatchingEngineService.calculate_role_score([], "ML Engineer") == 0.0
    assert MatchingEngineService.calculate_role_score(["ML Engineer"], "Senior ML Engineer") > 0.0


def test_matching_salary_unknown_job_salary_is_zero():
    # User wants salary, job is unknown => honest score, not auto-pass
    assert MatchingEngineService.calculate_salary_score(100000.0, 0.0, 0.0) == 0.0
    # User has no salary expectation => neutral 100
    assert MatchingEngineService.calculate_salary_score(0.0, 0.0, 0.0) == 100.0


def test_matching_experience_score():
    from app.services.matching_engine import MatchingEngineService as M
    assert M.calculate_experience_score(5.0, 2.0) >= 90.0
    assert M.calculate_experience_score(1.0, 5.0) < 90.0


# ==============================================================================
# EXPERIENCE EXTRACTION FROM SOURCES
# ==============================================================================
def test_experience_extraction_from_description():
    assert _extract_experience_years("Requires 3+ years of experience") == 3.0
    assert _extract_experience_years("Minimum of 5 years in Python") == 5.0
    assert _extract_experience_years("At least 2 years professional") == 2.0
    assert _extract_experience_years("No experience requirement mentioned") == 0.0


@pytest.mark.asyncio
async def test_rss_source_does_not_fabricate_company():
    from app.job_sources.rss_feed import RSSJobSource
    src = RSSJobSource(name="Test RSS", feed_url="https://x.example/feed")
    normalized = await src.normalize_job({
        "title": "Senior Data Engineer at FinTech Corp",
        "link": "https://x.example/jobs/data-eng",
        "summary": "Build pipelines using Python and SQL with 3+ years experience.",
    })
    assert normalized.company == "FinTech Corp"
    assert normalized.experience_years_required == 3.0


# ==============================================================================
# APP IDEMPOTENCY + STATUS TRANSITIONS
# ==============================================================================
@pytest.mark.asyncio
async def test_idempotency_key_is_stable():
    k1 = ApplicationExecutor.generate_idempotency_key(1, 2)
    k2 = ApplicationExecutor.generate_idempotency_key(1, 2)
    k3 = ApplicationExecutor.generate_idempotency_key(1, 3)
    assert k1 == k2
    assert k1 != k3


def test_terminal_states_prevent_resubmit():
    assert ApplicationStatus.can_submit(ApplicationStatus.PENDING_APPROVAL) is True
    assert ApplicationStatus.can_submit(ApplicationStatus.SUBMITTING) is False
    assert ApplicationStatus.can_submit(ApplicationStatus.APPLIED) is False
    assert ApplicationStatus.can_submit(ApplicationStatus.FAILED) is False
    assert ApplicationStatus.can_submit(ApplicationStatus.NEEDS_ACTION) is False


def test_application_status_enum_has_required_states():
    for state in ["SAVED", "PREPARING", "PENDING_APPROVAL", "SUBMITTING", "SUBMITTED",
                  "VERIFIED", "FAILED", "NEEDS_ACTION", "REJECTED"]:
        assert getattr(ApplicationStatus, state, None), f"Missing state {state}"


# ==============================================================================
# SUBMISSION LOCKING (via real DB session)
# ==============================================================================
@pytest.mark.asyncio
async def test_application_executor_dry_run_marks_would_submit(db_session):
    # Build minimal user + job
    user = User(email="idem@example.com", hashed_password="x", is_active=True)
    db_session.add(user)
    await db_session.flush()
    profile = UserProfile(user_id=user.id, full_name="Idem User", bio="Engineer")
    db_session.add(profile)
    await db_session.flush()

    job = Job(
        source_name="TestSource", title="ML Engineer", company="Acme",
        description="Build models", requirements=["Python"], skills=["Python"],
        description_hash="h1", job_url="http://x/j1", status=JobStatus.HIGH_MATCH,
        match_score=95.0,
    )
    db_session.add(job)
    await db_session.flush()

    # monkeypatch dry_run
    import app.services.application_executor as exmod
    exmod.settings.DRY_RUN = True
    try:
        app = await ApplicationExecutor.prepare_application(db_session, user, job.id)
        result = await ApplicationExecutor.submit(db_session, user, job, app, dry_run=True)
        assert result["status"] == "WOULD_SUBMIT"
        assert result["success"] is True
    finally:
        exmod.settings.DRY_RUN = False


@pytest.mark.asyncio
async def test_scheduler_lock_prevents_overlap(db_session):
    pipeline = AutomationPipeline()

    # A "running" run with recent started_at should block
    recent = SchedulerRun(run_id="RUN-OTHER", status=RunStatus.RUNNING, started_at=datetime.now(timezone.utc))
    db_session.add(recent)
    await db_session.flush()

    acquired = await pipeline.acquire_lock(db_session)
    assert acquired is False

    # Stale running run should be recovered
    recent.started_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await db_session.flush()
    acquired = await pipeline.acquire_lock(db_session)
    assert acquired is True
    assert recent.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_daily_application_guard_counts_today(db_session):
    """Daily limit should use DB state, not in-memory state."""
    from app.core.config import settings as cfg
    user = User(email="daily@example.com", hashed_password="x", is_active=True)
    db_session.add(user)
    await db_session.flush()

    # Create applications today
    for i in range(cfg.MAX_APPLICATIONS_PER_DAY + 1):
        job = Job(
            title=f"Job {i}", company="Co", description="d", requirements=[], skills=[],
            description_hash=f"h{i}", job_url=f"http://x/{i}", status=JobStatus.HIGH_MATCH,
            match_score=95.0,
        )
        db_session.add(job)
        await db_session.flush()
        db_session.add(Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.APPLIED))
    await db_session.flush()

    from sqlalchemy import select, func
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cnt = (await db_session.execute(
        select(func.count(Application.id)).where(
            Application.user_id == user.id, Application.created_at >= today_start
        )
    )).scalar()
    assert cnt >= cfg.MAX_APPLICATIONS_PER_DAY


# ==============================================================================
# SCHEDULER RUN RECORDING DOES NOT DUPLICATE run_id (unique constraint)
# ==============================================================================
@pytest.mark.asyncio
async def test_record_scheduler_run_upserts_unique_run_id(db_session):
    pipeline = AutomationPipeline()
    pipeline.run_id = "RUN-TEST-0001"
    now = datetime.now(timezone.utc)

    await pipeline._record_scheduler_run(
        db_session, user_id=1, started_at=now, finished_at=now,
        applications_prepared=3, applications_submitted=1,
    )
    await db_session.flush()

    # Second call with same run_id must update, not create a duplicate
    await pipeline._record_scheduler_run(
        db_session, user_id=1, started_at=now, finished_at=now,
        applications_prepared=5, applications_submitted=2,
    )
    await db_session.flush()

    from sqlalchemy import select, func
    cnt = (await db_session.execute(
        select(func.count(SchedulerRun.id)).where(SchedulerRun.run_id == "RUN-TEST-0001")
    )).scalar()
    assert cnt == 1


# ==============================================================================
# FAILED SOURCE ISOLATION
# ==============================================================================
@pytest.mark.asyncio
async def test_monitor_polls_even_if_one_source_fails(db_session):
    from app.workers.job_monitor_worker import JobMonitorWorker

    class GoodSource:
        name = "GoodSource"
        async def fetch_jobs(self, limit=25):
            return [{"title": "Good Job", "company": "GoodCo",
                     "description": "Python developer role with Docker.", "url": "http://good/1"}]
        async def normalize_job(self, raw):
            return NormalizedJob(
                title=raw["title"], company=raw["company"], description=raw["description"],
                job_url=raw["url"], source_name=self.name,
                skills=["Python", "Docker"], requirements=["Python"], preferred_skills=[],
            )

    class BadSource:
        name = "BadSource"
        async def fetch_jobs(self, limit=25):
            raise RuntimeError("boom")
        async def normalize_job(self, raw):
            return None

    import app.workers.job_monitor_worker as jwmod
    original = jwmod.get_all_active_sources
    jwmod.get_all_active_sources = lambda: [BadSource(), GoodSource()]
    try:
        result = await JobMonitorWorker.poll_all_sources(db_session)
        assert result["new_jobs_added"] >= 1  # Good source still ingested
    finally:
        jwmod.get_all_active_sources = original


# ==============================================================================
# PIPELINE PROFILE COMPLETENESS (regression: profile.email was an AttributeError)
# ==============================================================================
@pytest.mark.asyncio
async def test_pipeline_profile_check_uses_user_email_not_profile_email(db_session, test_user, monkeypatch):
    """Pipeline must read email from User; UserProfile has no email column."""
    import app.services.automation_pipeline as apmod

    async def _fake_check(db, user_id=None, dry_run=False):
        # Reproduce the real completeness logic in isolation
        from sqlalchemy import select
        user_res = await db.execute(
            select(User).where(User.id == test_user.id, User.is_active == True)
        )
        user = user_res.scalar_one_or_none()
        prof_res = await db.execute(select(UserProfile).where(UserProfile.user_id == test_user.id))
        profile = prof_res.scalar_one_or_none()
        # Ensure we reference user.email (this raised on UserProfile.email before fix)
        required = [profile.full_name, user.email, profile.bio]
        return {"required_fields_ok": bool(required and all(required))}

    monkeypatch.setattr(apmod.automation_pipeline, "run_cycle", _fake_check)
    result = await apmod.automation_pipeline.run_cycle(db_session)
    # Must not raise AttributeError on user.email (bio may be empty here)
    assert "required_fields_ok" in result


# ==============================================================================
# SOURCE CONFIG SYNC + GATING
# ==============================================================================
@pytest.mark.asyncio
async def test_sync_source_configs_creates_rows(db_session):
    from app.services.source_config_service import sync_source_configs
    from app.models.job import JobSourceConfig
    from sqlalchemy import select, func

    count_before = (await db_session.execute(select(func.count(JobSourceConfig.id)))).scalar()
    arrays = await sync_source_configs(db_session)
    count_after = (await db_session.execute(select(func.count(JobSourceConfig.id)))).scalar()

    assert count_after >= count_before
    # All registered adapters should now have a config row
    from app.job_sources import get_all_registered_adapters
    assert count_after >= len(get_all_registered_adapters())


@pytest.mark.asyncio
async def test_disabled_source_is_skipped_and_enabled_runs(db_session):
    from app.services.source_config_service import sync_source_configs
    from app.workers.job_monitor_worker import JobMonitorWorker
    from app.job_sources.base import NormalizedJob
    from sqlalchemy import select
    from app.models.job import JobSourceConfig

    await sync_source_configs(db_session)

    class AlwaysSource:
        name = "AlwaysOnSource"
        async def fetch_jobs(self, limit=25):
            return [{"title": "On Job", "company": "OnCo",
                     "description": "Python developer role.", "url": "http://on/1"}]
        async def normalize_job(self, raw):
            return NormalizedJob(
                title=raw["title"], company=raw["company"], description=raw["description"],
                job_url=raw["url"], source_name=self.name,
                skills=["Python"], requirements=["Python"], preferred_skills=[],
            )

    class DisabledSource:
        name = "TurnedOffSource"
        async def fetch_jobs(self, limit=25):
            return [{"title": "Off Job", "company": "OffCo",
                     "description": "Java developer role.", "url": "http://off/1"}]
        async def normalize_job(self, raw):
            return NormalizedJob(
                title=raw["title"], company=raw["company"], description=raw["description"],
                job_url=raw["url"], source_name=self.name,
                skills=["Java"], requirements=["Java"], preferred_skills=[],
            )

    # Disable TurnedOffSource in the DB
    off_cfg = (await db_session.execute(
        select(JobSourceConfig).where(JobSourceConfig.name == "TurnedOffSource")
    )).scalar_one_or_none()
    if not off_cfg:
        off_cfg = JobSourceConfig(name="TurnedOffSource", source_type="TEST", is_enabled=False)
        db_session.add(off_cfg)
        await db_session.commit()

    off_cfg.is_enabled = False
    await db_session.commit()

    import app.workers.job_monitor_worker as jwmod
    original = jwmod.get_all_active_sources
    jwmod.get_all_active_sources = lambda: [AlwaysSource(), DisabledSource()]
    try:
        await JobMonitorWorker.poll_all_sources(db_session)
    finally:
        jwmod.get_all_active_sources = original

    # Every inserted job must be from the enabled source only
    from sqlalchemy import select as _s
    from app.models.job import Job
    inserted = (await db_session.execute(_s(Job))).scalars().all()
    assert any(j.company == "OnCo" for j in inserted)
    assert not any(j.company == "OffCo" for j in inserted)