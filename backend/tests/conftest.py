import os
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import all models so Base metadata has all tables registered
import app.models.user as _m_user
import app.models.resume as _m_resume
import app.models.job as _m_job
import app.models.application as _m_app
import app.models.automation as _m_auto
import app.models.notification as _m_notif
import app.models.audit as _m_audit

from app.main import app as fastapi_app
from app.core.database import Base
from app.api.deps import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserProfile
from app.models.automation import AutomationSettings

TEST_DB_FILE = "./test_agent_suite.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestAsyncSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        email="testuser@example.com",
        hashed_password=get_password_hash("Secret123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        full_name="Alex Mercer",
        current_title="Senior AI Engineer",
        years_experience=5.0,
    )
    db_session.add(profile)

    auto_settings = AutomationSettings(
        user_id=user.id,
        is_scheduler_enabled=True,
    )
    db_session.add(auto_settings)

    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "testuser@example.com", "password": "Secret123!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
