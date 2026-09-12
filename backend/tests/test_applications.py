import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_application_lifecycle_and_approval(client: AsyncClient, auth_headers):
    # 1. Create a job first
    job_payload = {
        "title": "Fullstack AI Engineer",
        "company": "NeuralStack Labs",
        "location": "Remote",
        "description": "Building fullstack AI agent applications with Python, FastAPI, and React.",
        "skills_required": ["Python", "FastAPI", "React", "Docker"],
    }
    job_res = await client.post("/api/v1/jobs/manual", json=job_payload, headers=auth_headers)
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    # 2. Prepare application
    prep_res = await client.post(
        f"/api/v1/applications/prepare/{job_id}",
        headers=auth_headers,
    )
    assert prep_res.status_code == 200
    app_data = prep_res.json()
    assert app_data["job_id"] == job_id
    assert "cover_letter_text" in app_data
    app_id = app_data["id"]

    # 3. Approve application (Human-in-the-loop)
    approve_res = await client.post(
        f"/api/v1/applications/{app_id}/approve",
        headers=auth_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["is_user_approved"] is True

    # 4. Mark as submitted
    submit_res = await client.post(
        f"/api/v1/applications/{app_id}/mark-submitted",
        json={"application_id": app_id, "submission_method": "MANUAL_APPROVED"},
        headers=auth_headers,
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "APPLIED"

    # 5. List applications
    list_res = await client.get("/api/v1/applications", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
