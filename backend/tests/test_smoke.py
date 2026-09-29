"""Smoke test: boots the FastAPI app against a scratch DB and exercises key endpoints."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./smoke_test.db"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["DRY_RUN"] = "true"

import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport

from app.core.database import Base


@pytest.fixture(scope="function")
async def bootstrap():
    # Re-import app so config is set before modules load
    from app.main import app as fastapi_app
    from app.api.deps import get_db
    from app.core.database import AsyncSessionLocal

    engine = create_async_engine("sqlite+aiosqlite:///./smoke_test.db", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture(scope="function")
async def auth(bootstrap):
    from app.core.security import get_password_hash
    from app.core.database import Base as B
    # register returns a Token directly
    res = await bootstrap.post("/api/v1/auth/register", json={
        "email": "smoke@test.com", "password": "SmokePass123!", "full_name": "Smoke User"
    })
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_health_ready(bootstrap):
    r = await bootstrap.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

    r = await bootstrap.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_root(bootstrap):
    r = await bootstrap.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"


async def test_automation_settings_roundtrip(bootstrap, auth):
    r = await bootstrap.get("/api/v1/automation/settings", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert "is_scheduler_enabled" in data

    r = await bootstrap.put("/api/v1/automation/settings", headers=auth, json={
        "min_match_score": 85.0, "is_scheduler_enabled": True
    })
    assert r.status_code == 200
    assert r.json()["min_match_score"] == 85.0


async def test_jobs_list(bootstrap, auth):
    r = await bootstrap.get("/api/v1/jobs", headers=auth)
    assert r.status_code == 200
    jobs = r.json()
    assert isinstance(jobs, list)


async def test_run_now_dry(bootstrap, auth):
    r = await bootstrap.post("/api/v1/automation/run-now?dry_run=true", headers=auth)
    # run may fail if no active profile completed, but endpoint must respond
    assert r.status_code == 200
    body = r.json()
    # Phase 5 vocabulary: run status reflects real outcomes, not a generic
    # "completed" regardless of what actually happened. Lowercase values are
    # deliberately NOT tolerated -- accepting them previously hid a real bug
    # where a worker compared against "failed" and exited 0 on every crash.
    assert body["status"] in {
        "SUCCESS", "PARTIAL_SUCCESS", "FAILED", "SKIPPED", "INCOMPLETE", "RUNNING",
    }


async def test_analytics_dashboard(bootstrap, auth):
    r = await bootstrap.get("/api/v1/analytics/dashboard", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data