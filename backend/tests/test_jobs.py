import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_job(client: AsyncClient, auth_headers):
    payload = {
        "title": "Senior Machine Learning Engineer",
        "company": "Anthropic AI Labs",
        "location": "San Francisco, CA (Remote)",
        "remote_type": "REMOTE",
        "employment_type": "FULL_TIME",
        "source_name": "Direct",
        "job_url": "https://example.com/careers/ml-eng-101",
        "description": "We are seeking a Senior ML Engineer proficient in PyTorch, LLMs, Transformer architectures, and RAG pipelines.",
        "skills": ["Python", "PyTorch", "LLMs", "RAG", "FastAPI"],
    }
    response = await client.post("/api/v1/jobs/manual", json=payload, headers=auth_headers)
    assert response.status_code == 201
    job_data = response.json()
    assert job_data["title"] == payload["title"]
    assert job_data["company"] == payload["company"]
    job_id = job_data["id"]

    # List jobs
    list_response = await client.get("/api/v1/jobs", headers=auth_headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert len(list_data) >= 1
    assert any(j["id"] == job_id for j in list_data)

    # Get single job
    get_response = await client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == job_id


@pytest.mark.asyncio
async def test_job_status_update(client: AsyncClient, auth_headers):
    payload = {
        "title": "Backend Software Engineer",
        "company": "CloudScale Inc",
        "location": "New York, NY",
        "description": "Building high-throughput microservices in Go and Python.",
        "skills": ["Python", "Go", "PostgreSQL", "Docker"],
    }
    create_resp = await client.post("/api/v1/jobs/manual", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # Update status to ARCHIVED
    update_resp = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={"status": "ARCHIVED"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "ARCHIVED"
