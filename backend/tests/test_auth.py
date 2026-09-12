import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "password": "Password123!",
        "full_name": "Jane Doe",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200 or response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_login_user(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "Secret123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
