"""Regression tests for source-failure isolation in the job monitor.

The original implementation cached JobSourceConfig ORM instances and read their
attributes after a rollback. SQLAlchemy expires every object in a session on
rollback, so those reads attempted an implicit lazy load and raised
MissingGreenlet ("greenlet_spawn has not been called") in async code -- killing
the whole cycle whenever a single source failed.

The cycle must now survive any number of failing sources and still commit the
jobs discovered from the healthy ones.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.job_sources.base import JobSource, NormalizedJob
from app.models.job import Job, JobSourceConfig, JobSourceHealth
from app.workers.job_monitor_worker import job_monitor_worker


class _FailingSource(JobSource):
    """A source that always raises, to force the rollback path."""

    def __init__(self, name: str, boom: Exception):
        super().__init__(name=name, source_type="RSS")
        self._boom = boom
        self.fetch_calls = 0

    async def fetch_jobs(self, limit: int = 25):
        self.fetch_calls += 1
        raise self._boom

    async def normalize_job(self, raw_job):
        return None


class _GoodSource(JobSource):
    """A source that returns one deterministic job."""

    def __init__(self, name: str, tag: str):
        super().__init__(name=name, source_type="RSS")
        self._tag = tag

    async def fetch_jobs(self, limit: int = 25):
        return [{"id": f"{self._tag}-1"}]

    async def normalize_job(self, raw_job):
        # description_hash and normalized_url are computed properties.
        return NormalizedJob(
            source_name=self.name,
            external_job_id=f"{self._tag}-1",
            title=f"{self._tag} Engineer",
            company=f"{self._tag} Corp",
            location="Remote",
            description=f"Work at {self._tag} Corp building reliable systems.",
            job_url=f"https://{self._tag.lower()}.example.com/jobs/1",
            skills=["Python"],
            requirements=["Python"],
            experience_years_required=3,
        )


def _patch_sources(monkeypatch, sources):
    """Replace the active source list for one poll."""
    monkeypatch.setattr(
        "app.workers.job_monitor_worker.get_all_active_sources",
        lambda: list(sources),
    )


async def _ensure_configs(db: AsyncSession, names, enabled=True):
    for name in names:
        db.add(
            JobSourceConfig(
                name=name, source_type="RSS", url_or_endpoint="", is_enabled=enabled
            )
        )
    await db.commit()


async def _configs(db: AsyncSession):
    res = await db.execute(select(JobSourceConfig))
    return {c.name: c for c in res.scalars().all()}


@pytest.mark.asyncio
async def test_failing_source_does_not_kill_cycle(db_session: AsyncSession, monkeypatch):
    """A source that raises must not abort the cycle or lose the other sources' jobs."""
    boom = _FailingSource("Flaky Source", RuntimeError("upstream is down"))
    good = _GoodSource("Good Source", "Alpha")
    _patch_sources(monkeypatch, [boom, good])
    await _ensure_configs(db_session, [boom.name, good.name])

    result = await job_monitor_worker.poll_all_sources(db=db_session)

    # The healthy source's job was ingested and committed.
    assert result["total_discovered"] == 1
    assert result["new_jobs_added"] == 1
    assert len(result["job_ids"]) == 1
    assert isinstance(result["job_ids"][0], int)

    job = (await db_session.execute(
        select(Job).where(Job.id == result["job_ids"][0])
    )).scalar_one()
    assert job.title == "Alpha Engineer"

    # The failure is recorded and did not poison the healthy source's state.
    cfgs = await _configs(db_session)
    assert cfgs[boom.name].consecutive_failures == 1
    assert cfgs[boom.name].health_status == JobSourceHealth.DEGRADED
    assert cfgs[good.name].health_status == JobSourceHealth.HEALTHY
    assert cfgs[good.name].consecutive_failures == 0


@pytest.mark.asyncio
async def test_multiple_consecutive_failures_still_survive(db_session: AsyncSession, monkeypatch):
    """Several failing sources before a good one must not break anything.

    This is the case that used to raise MissingGreenlet: the rollback from an
    earlier source expired the config instance a later iteration then read.
    """
    import httpx

    b1 = _FailingSource("Down One", RuntimeError("down 1"))
    b2 = _FailingSource("Down Two", httpx.ConnectError("connection refused"))
    b3 = _FailingSource("Down Three", TimeoutError("down 3"))
    good = _GoodSource("Good Source", "Beta")
    _patch_sources(monkeypatch, [b1, b2, b3, good])
    await _ensure_configs(db_session, [b1.name, b2.name, b3.name, good.name])

    result = await job_monitor_worker.poll_all_sources(db=db_session)

    assert result["new_jobs_added"] == 1
    assert result["total_discovered"] == 1
    assert result["duplicates_skipped"] == 0

    cfgs = await _configs(db_session)
    for src in (b1, b2, b3):
        assert cfgs[src.name].health_status == JobSourceHealth.DEGRADED
        assert cfgs[src.name].consecutive_failures == 1
    assert cfgs[good.name].health_status == JobSourceHealth.HEALTHY


@pytest.mark.asyncio
async def test_health_escalates_to_failed_after_three_strikes(db_session: AsyncSession, monkeypatch):
    """Health must escalate DEGRADED -> FAILED and reset to HEALTHY on recovery."""
    bad = _FailingSource("Unstable Source", RuntimeError("still down"))
    _patch_sources(monkeypatch, [bad])
    await _ensure_configs(db_session, [bad.name])

    for expected, strikes in (
        (JobSourceHealth.DEGRADED, 1),
        (JobSourceHealth.DEGRADED, 2),
        (JobSourceHealth.FAILED, 3),
    ):
        await job_monitor_worker.poll_all_sources(db=db_session)
        cfg = (await _configs(db_session))[bad.name]
        assert cfg.health_status == expected
        assert cfg.consecutive_failures == strikes

    # Recovery: the same source name now succeeds and resets the streak.
    recovered = _GoodSource("Unstable Source", "Delta")
    _patch_sources(monkeypatch, [recovered])
    await job_monitor_worker.poll_all_sources(db=db_session)

    cfg = (await _configs(db_session))[bad.name]
    assert cfg.health_status == JobSourceHealth.HEALTHY
    assert cfg.consecutive_failures == 0


@pytest.mark.asyncio
async def test_disabled_source_is_skipped_entirely(db_session: AsyncSession, monkeypatch):
    """A disabled source must not be fetched at all."""
    off = _GoodSource("Disabled Source", "Disabled")
    on = _GoodSource("Enabled Source", "Enabled")
    _patch_sources(monkeypatch, [off, on])
    await _ensure_configs(db_session, [off.name, on.name])

    cfg = (await _configs(db_session))[off.name]
    cfg.is_enabled = False
    await db_session.commit()

    result = await job_monitor_worker.poll_all_sources(db=db_session)

    assert result["new_jobs_added"] == 1
    titles = (await db_session.execute(select(Job.title))).scalars().all()
    assert "Enabled Engineer" in titles
    assert "Disabled Engineer" not in titles


@pytest.mark.asyncio
async def test_all_sources_failing_still_returns_a_result(db_session: AsyncSession, monkeypatch):
    """Total failure yields honest zeros rather than an exception."""
    b1 = _FailingSource("Down A", RuntimeError("a"))
    b2 = _FailingSource("Down B", RuntimeError("b"))
    _patch_sources(monkeypatch, [b1, b2])
    await _ensure_configs(db_session, [b1.name, b2.name])

    result = await job_monitor_worker.poll_all_sources(db=db_session)

    assert result == {
        "total_discovered": 0,
        "new_jobs_added": 0,
        "duplicates_skipped": 0,
        "job_ids": [],
    }
