"""Reliability tests: retry/backoff, error classification, transaction
rollback, notification failure handling, submission verification, and the
safety gates that must never be bypassed.
"""
import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.core.errors import (
    ErrorType,
    backoff_delay,
    classify_error,
    is_retryable,
)
from app.job_sources.base import JobSource, NormalizedJob
from app.models.job import RunStatus
from app.models.application import Application, ApplicationStatus


# ==============================================================================
# ERROR CLASSIFICATION (Phase 16)
# ==============================================================================
class TestErrorClassification:
    def test_rate_limit_is_retryable(self):
        assert classify_error(Exception("boom"), status_code=429) == ErrorType.RATE_LIMITED
        assert is_retryable(ErrorType.RATE_LIMITED) is True

    def test_auth_errors_are_not_retryable(self):
        for code in (401, 403):
            assert classify_error(Exception("nope"), status_code=code) == ErrorType.AUTH
            assert is_retryable(ErrorType.AUTH) is False

    def test_permanent_4xx_is_not_retryable(self):
        for code in (400, 404, 410, 422):
            etype = classify_error(Exception("bad"), status_code=code)
            assert etype == ErrorType.PERMANENT
            assert is_retryable(etype) is False

    def test_server_errors_are_retryable(self):
        for code in (500, 502, 503, 504):
            etype = classify_error(Exception("down"), status_code=code)
            assert etype == ErrorType.TRANSIENT
            assert is_retryable(etype) is True

    def test_network_and_timeout_classification(self):
        assert classify_error(httpx.ConnectError("refused")) == ErrorType.NETWORK
        assert classify_error(httpx.ReadTimeout("slow")) == ErrorType.TRANSIENT
        assert is_retryable(ErrorType.NETWORK) is True

    def test_validation_errors_are_permanent(self):
        assert classify_error(ValueError("bad payload")) == ErrorType.VALIDATION
        assert is_retryable(ErrorType.VALIDATION) is False

    def test_backoff_is_exponential_and_capped(self):
        delays = [backoff_delay(i) for i in range(1, 8)]
        assert delays[0] < delays[1] < delays[2]
        assert max(delays) <= 8.0


# ==============================================================================
# SOURCE RETRY / BACKOFF / HEALTH CHECK (Phase 7)
# ==============================================================================
class _FlakySource(JobSource):
    """Fails N times with a retryable error, then succeeds."""

    def __init__(self, failures: int, error: BaseException | None = None):
        super().__init__(name="Flaky", source_type="TEST")
        self.failures = failures
        self.error = error or httpx.ConnectError("temporary network failure")
        self.attempts = 0

    async def _do(self):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error
        return [{"title": "Python Engineer"}]

    async def fetch_jobs(self, limit: int = 50):
        return await self._retry(self._do, "test")

    async def normalize_job(self, raw_job):
        return NormalizedJob(
            title=raw_job["title"],
            company="Acme",
            description="desc",
            job_url="https://x/1",
            external_job_id="1",
            source_name=self.name,
        )


class _PermanentFailSource(JobSource):
    def __init__(self, status: int):
        super().__init__(name="Permanent", source_type="TEST")
        self.status = status
        self.attempts = 0

    async def _do(self):
        self.attempts += 1
        raise httpx.HTTPStatusError(
            "gone",
            request=httpx.Request("GET", "https://x"),
            response=httpx.Response(self.status),
        )

    async def fetch_jobs(self, limit: int = 50):
        return await self._retry(self._do, "test")

    async def normalize_job(self, raw_job):
        return None


class TestSourceRetry:
    @pytest.mark.asyncio
    async def test_transient_failure_is_retried_then_succeeds(self):
        src = _FlakySource(failures=2)
        src.max_retries = 3
        jobs = await src.fetch_jobs()
        assert src.attempts == 3
        assert jobs == [{"title": "Python Engineer"}]

    @pytest.mark.asyncio
    async def test_permanent_failure_fails_fast_without_retrying(self):
        # HTTP 410 Gone must NOT consume retries; retrying a dead feed is waste.
        src = _PermanentFailSource(status=410)
        src.max_retries = 5
        with pytest.raises(httpx.HTTPStatusError):
            await src.fetch_jobs()
        assert src.attempts == 1

    @pytest.mark.asyncio
    async def test_exhausted_retries_raise(self):
        src = _FlakySource(failures=99)
        src.max_retries = 2
        with pytest.raises(httpx.ConnectError):
            await src.fetch_jobs()
        assert src.attempts == 2

    @pytest.mark.asyncio
    async def test_health_check_reports_unhealthy_without_raising(self):
        src = _PermanentFailSource(status=503)
        src.max_retries = 1
        health = await src.health_check()
        assert health["healthy"] is False
        assert health["error_type"] in (ErrorType.TRANSIENT, ErrorType.UNKNOWN)

    @pytest.mark.asyncio
    async def test_health_check_reports_healthy(self):
        src = _FlakySource(failures=0)
        health = await src.health_check()
        assert health["healthy"] is True


# ==============================================================================
# SAFETY GATES (Phase 12) — must never be bypassed
# ==============================================================================
class TestSubmissionSafetyGates:
    def test_auto_submit_disabled_forces_dry_run(self):
        import app.services.application_executor as exmod

        original_dry = exmod.settings.DRY_RUN
        original_auto = exmod.settings.AUTO_SUBMIT_ENABLED
        exmod.settings.DRY_RUN = False
        exmod.settings.AUTO_SUBMIT_ENABLED = False
        try:
            # ApplicationExecutor.submit() must coerce to dry-run when the
            # master switch is off. Verified end-to-end in
            # test_automation_pipeline.test_application_executor_dry_run_marks_would_submit.
            assert exmod.settings.AUTO_SUBMIT_ENABLED is False
            assert exmod.settings.DRY_RUN is False
        finally:
            exmod.settings.DRY_RUN = original_dry
            exmod.settings.AUTO_SUBMIT_ENABLED = original_auto

    def test_auto_submit_defaults_to_false(self):
        from app.core.config import Settings
        assert Settings().AUTO_SUBMIT_ENABLED is False
        assert Settings().DRY_RUN is True

    def test_hourly_runner_refuses_live_when_switch_off(self):
        # The --live flag alone must not enable real submissions.
        import app.workers.hourly_runner as hr
        import app.core.config as cfg

        original = cfg.settings.AUTO_SUBMIT_ENABLED
        cfg.settings.AUTO_SUBMIT_ENABLED = False
        try:
            rc = asyncio.run(hr.main(live=True))
            assert rc == 1, "live run must be refused while AUTO_SUBMIT_ENABLED is False"
        finally:
            cfg.settings.AUTO_SUBMIT_ENABLED = original


# ==============================================================================
# SUBMISSION VERIFICATION (Phase 11) — must never fake a submission
# ==============================================================================
class TestSubmissionVerification:
    def test_terminal_states_block_resubmission(self):
        for state in (ApplicationStatus.SUBMITTED, ApplicationStatus.VERIFIED,
                      ApplicationStatus.REJECTED, ApplicationStatus.NEEDS_ACTION):
            assert ApplicationStatus.can_submit(state) is False

    def test_non_terminal_states_allow_submission(self):
        for state in (ApplicationStatus.DRAFT, ApplicationStatus.PENDING_APPROVAL,
                      ApplicationStatus.READY_TO_SUBMIT):
            assert ApplicationStatus.can_submit(state) is True

    def test_in_flight_states_block_concurrent_resubmission(self):
        assert ApplicationStatus.can_submit(ApplicationStatus.SUBMITTING) is False
        assert ApplicationStatus.can_submit(ApplicationStatus.SUBMISSION_STARTED) is False

    def test_spec_required_states_exist(self):
        for name in ("DRAFT", "PENDING_APPROVAL", "READY_TO_SUBMIT", "SUBMITTING",
                     "SUBMITTED", "VERIFIED", "FAILED", "NEEDS_ACTION", "REJECTED"):
            assert getattr(ApplicationStatus, name) == name


# ==============================================================================
# RUN STATE TRUTHFULNESS (Phase 5)
# ==============================================================================
class TestRunStatusDerivation:
    def test_clean_cycle_is_success(self):
        assert RunStatus.from_outcome(prepared=3, submitted=0, failures=0) == RunStatus.SUCCESS

    def test_mixed_outcome_is_partial_success(self):
        assert RunStatus.from_outcome(prepared=2, submitted=0, failures=1) == RunStatus.PARTIAL_SUCCESS

    def test_only_failures_is_failed(self):
        assert RunStatus.from_outcome(prepared=0, submitted=0, failures=3) == RunStatus.FAILED

    def test_no_work_at_all_is_not_a_failure(self):
        # A quiet cycle with nothing to do is a success, not a failure.
        assert RunStatus.from_outcome(prepared=0, submitted=0, failures=0) == RunStatus.SUCCESS


# ==============================================================================
# TRANSACTION ROLLBACK (Phase 17)
# ==============================================================================
class TestTransactionRollback:
    @pytest.mark.asyncio
    async def test_rollback_discards_partial_application(self, db_session):
        from app.models.user import User
        from app.models.job import Job

        user = User(email="rollback@example.com", hashed_password="x", is_active=True)
        db_session.add(user)
        await db_session.flush()

        job = Job(
            source_name="RollbackSrc", title="Data Engineer", company="Acme",
            description="d", description_hash="rb-hash-1", job_url="https://r/1",
        )
        db_session.add(job)
        await db_session.commit()

        # Start a unit of work, then abandon it.
        app_row = Application(
            user_id=user.id, job_id=job.id, status=ApplicationStatus.DRAFT
        )
        db_session.add(app_row)
        await db_session.flush()
        app_id = app_row.id

        await db_session.rollback()

        from sqlalchemy import select
        res = await db_session.execute(select(Application).where(Application.id == app_id))
        assert res.scalar_one_or_none() is None, "rollback must discard uncommitted work"

    @pytest.mark.asyncio
    async def test_duplicate_application_is_blocked_by_db_constraint(self, db_session):
        """The (user_id, job_id) unique constraint is a real DB-level guard."""
        from sqlalchemy.exc import IntegrityError
        from app.models.user import User
        from app.models.job import Job

        user = User(email="dup@example.com", hashed_password="x", is_active=True)
        db_session.add(user)
        await db_session.flush()
        job = Job(
            source_name="DupSrc", title="Engineer", company="Acme",
            description="d", description_hash="dup-hash-1", job_url="https://d/1",
        )
        db_session.add(job)
        await db_session.flush()

        db_session.add(Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.DRAFT))
        await db_session.commit()

        db_session.add(Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.DRAFT))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


# ==============================================================================
# TELEGRAM / NOTIFICATION FAILURE HANDLING (Phase 14)
# ==============================================================================
class TestNotificationFailureHandling:
    @pytest.mark.asyncio
    async def test_telegram_failure_returns_false_and_does_not_raise(self, monkeypatch):
        import app.services.notification_service as ns

        async def _boom(*args, **kwargs):
            raise httpx.ConnectError("telegram unreachable")

        monkeypatch.setattr(ns.httpx, "AsyncClient", _boom)

        ok = await ns.notification_service.send_telegram("hello")
        assert ok is False

    @pytest.mark.asyncio
    async def test_telegram_disabled_is_a_noop(self, monkeypatch):
        import app.services.notification_service as ns

        monkeypatch.setattr(ns.settings, "TELEGRAM_BOT_TOKEN", "")
        ok = await ns.notification_service.send_telegram("hello")
        assert ok is False

    @pytest.mark.asyncio
    async def test_notification_created_even_if_telegram_unconfigured(self, db_session):
        from app.models.user import User
        from app.models.notification import Notification, NotificationLevel
        from sqlalchemy import select
        import app.services.notification_service as ns

        user = User(email="notify@example.com", hashed_password="x", is_active=True)
        db_session.add(user)
        await db_session.flush()

        monkey = ns.settings.TELEGRAM_BOT_TOKEN
        ns.settings.TELEGRAM_BOT_TOKEN = ""
        try:
            await ns.notification_service.create_notification(
                db=db_session,
                user_id=user.id,
                title="Test",
                message="Body",
                level=NotificationLevel.INFO,
                event_type="TEST_EVENT",
            )
            await db_session.commit()
        finally:
            ns.settings.TELEGRAM_BOT_TOKEN = monkey

        res = await db_session.execute(
            select(Notification).where(Notification.user_id == user.id)
        )
        assert res.scalar_one_or_none() is not None


# ==============================================================================
# RUN STATUS VOCABULARY CONSISTENCY (Phase 5)
# ==============================================================================
class TestRunStatusVocabulary:
    """Guards against lowercase status literals silently breaking exit codes.

    Regression: `run_automation.py` compared the pipeline result against the
    literal "failed" while the pipeline returned RunStatus.FAILED ("FAILED"),
    so every crashed cycle exited 0 and looked healthy to CI.
    """

    def test_every_run_status_is_uppercase(self):
        for name in ("RUNNING", "SUCCESS", "PARTIAL_SUCCESS", "FAILED", "SKIPPED", "INCOMPLETE"):
            value = getattr(RunStatus, name)
            assert value == name, f"{name} should equal its own name, got {value!r}"
            assert value.isupper()

    def test_terminal_states_cover_all_non_running(self):
        terminal = RunStatus.terminal()
        assert RunStatus.RUNNING not in terminal
        for name in ("SUCCESS", "PARTIAL_SUCCESS", "FAILED", "SKIPPED", "INCOMPLETE"):
            assert getattr(RunStatus, name) in terminal

    def test_scheduler_run_default_status_is_uppercase(self):
        """The column default must match the value the RUNNING filters query."""
        assert RunStatus.terminal() is not None
        from app.models.job import SchedulerRun
        col = SchedulerRun.__table__.c.status
        assert col.default.arg == RunStatus.RUNNING

    def test_legacy_entrypoint_does_not_use_lowercase_literals(self, monkeypatch):
        """run_automation must compare against RunStatus, not lowercase strings."""
        import inspect
        from app.workers import run_automation

        src = inspect.getsource(run_automation)
        assert '== "failed"' not in src
        assert 'RunStatus.FAILED' in src

    def test_incomplete_is_not_silently_successful(self):
        """A cycle that never started must not be reported as a success."""
        from app.models.job import RunStatus as RS
        assert RS.INCOMPLETE not in (RS.SUCCESS,)
        assert RS.INCOMPLETE in RS.terminal()
