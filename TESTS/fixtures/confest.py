"""
Shared pytest fixtures used across unit, integration, and E2E tests.
"""
import asyncio
import os
import sys

import pytest
import pytest_asyncio

# Add api/ to path for all tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))


# ── Event loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test DB engine. Requires DATABASE_URL env var."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from db.session import Base
    import db.models.user
    import db.models.conversation
    import db.models.knowledge
    import db.models.memory
    import db.models.workflow
    import db.models.billing
    import db.models.audit
    import db.models.integrations

    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/catai_test",
    )
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide a clean DB session that rolls back after each test."""
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(test_engine) as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── HTTP client fixture ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session):
    """Provide an async test client for the FastAPI app."""
    from httpx import AsyncClient, ASGITransport
    from main import create_app
    from db.session import get_db

    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Auth fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user and return it with auth tokens."""
    from db.models.user import User, Organization, Membership, RoleEnum
    from core.security import hash_password, create_access_token

    user = User(
        email="test@catai.test",
        name="Test User",
        hashed_password=hash_password("testpass123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    org = Organization(
        name="Test Org",
        slug=f"test-org-{user.id[:8]}",
        owner_id=user.id,
    )
    db_session.add(org)
    await db_session.flush()

    db_session.add(Membership(user_id=user.id, org_id=org.id, role=RoleEnum.owner))
    await db_session.flush()

    access_token = create_access_token({"sub": user.id, "email": user.email})

    return {
        "user": user,
        "org": org,
        "access_token": access_token,
        "headers": {
            "Authorization": f"Bearer {access_token}",
            "X-Workspace-Id": org.id,
        },
    }


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create a superadmin test user."""
    from db.models.user import User
    from core.security import hash_password, create_access_token

    user = User(
        email="superadmin@catai.test",
        name="Super Admin",
        hashed_password=hash_password("adminpass123"),
        is_active=True,
        is_superadmin=True,
    )
    db_session.add(user)
    await db_session.flush()

    access_token = create_access_token({"sub": user.id, "email": user.email})

    return {
        "user": user,
        "access_token": access_token,
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


# ── Mock provider fixtures ────────────────────────────────────────────────────

@pytest.fixture
def mock_openai_stream(monkeypatch):
    """
    Mock OpenAI streaming to return a fixed response without API calls.
    """
    async def _fake_stream(messages, model="gpt-4o", **kwargs):
        for token in ["Hello", ", ", "world", "!"]:
            yield token

    monkeypatch.setattr(
        "ai.providers.openai.OpenAIProvider.stream_completion",
        _fake_stream,
    )
    return _fake_stream


@pytest.fixture
def mock_openai_complete(monkeypatch):
    """Mock non-streaming OpenAI completion."""
    async def _fake_complete(messages, model="gpt-4o", **kwargs):
        return {
            "content": "Mocked response from the test fixture.",
            "tokens_in": 10,
            "tokens_out": 8,
            "finish_reason": "stop",
        }

    monkeypatch.setattr(
        "ai.providers.openai.OpenAIProvider.chat_completion",
        _fake_complete,
    )
    return _fake_complete