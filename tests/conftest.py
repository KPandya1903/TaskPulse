"""
Pytest Configuration and Fixtures for Pulse Authentication Tests.

This module provides shared fixtures for testing the Pulse authentication system.
It sets up an in-memory SQLite database for fast test execution and provides
utilities for creating test users and generating authentication tokens.

TDD Note: These fixtures import from modules that don't exist yet. Tests will
fail at the import stage initially, which is expected in the red phase of TDD.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# These imports will fail initially - this is expected for TDD (red phase)
# The implementation will be created to make these imports work
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.task import Task  # noqa: F401


# Test database URL - using async SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create an event loop for the test session.

    This fixture provides a single event loop that persists across the entire
    test session, which is required for async fixtures and tests.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """
    Create an async SQLAlchemy engine for testing.

    Uses an in-memory SQLite database with StaticPool to ensure the same
    connection is reused across the session, which is required for in-memory
    SQLite databases to persist data.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a database session for each test.

    Each test gets its own session that is rolled back after the test completes,
    ensuring test isolation. The session is bound to the test's async engine.
    """
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async HTTP client for testing FastAPI endpoints.

    This fixture overrides the database dependency to use the test database
    session, ensuring tests run against the in-memory test database.

    Usage:
        async def test_example(client: AsyncClient):
            response = await client.get("/api/v1/some-endpoint")
            assert response.status_code == 200
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """
    Create a standard test user in the database.

    Returns a User object with:
    - email: test@example.com
    - password: testpassword123 (hashed)
    - is_active: True
    - is_superuser: False

    This user can be used for login tests and protected endpoint tests.
    """
    user = User(
        id=uuid4(),
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def inactive_user(db_session: AsyncSession) -> User:
    """
    Create an inactive test user in the database.

    Returns a User object with:
    - email: inactive@example.com
    - password: testpassword123 (hashed)
    - is_active: False

    This user is used to test that inactive users cannot log in.
    """
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Inactive User",
        is_active=False,
        is_superuser=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def superuser(db_session: AsyncSession) -> User:
    """
    Create a superuser test account in the database.

    Returns a User object with:
    - email: admin@example.com
    - password: adminpassword123 (hashed)
    - is_active: True
    - is_superuser: True

    This user can be used for testing admin-only endpoints.
    """
    user = User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password=hash_password("adminpassword123"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """
    Generate authentication headers with a valid access token.

    Returns a dictionary with the Authorization header containing a valid
    Bearer token for the test user. Use this fixture when testing protected
    endpoints that require authentication.

    Usage:
        async def test_protected_endpoint(client, auth_headers):
            response = await client.get("/api/v1/protected", headers=auth_headers)
    """
    access_token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def expired_auth_headers(test_user: User) -> dict[str, str]:
    """
    Generate authentication headers with an expired access token.

    Returns a dictionary with the Authorization header containing an expired
    Bearer token. Use this fixture to test that expired tokens are rejected.
    """
    # Create a token that expired 1 hour ago
    access_token = create_access_token(
        subject=str(test_user.id),
        expires_delta=timedelta(hours=-1),
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def invalid_auth_headers() -> dict[str, str]:
    """
    Generate authentication headers with an invalid token.

    Returns a dictionary with the Authorization header containing a malformed
    token that should be rejected by the authentication system.
    """
    return {"Authorization": "Bearer invalid.token.here"}


@pytest_asyncio.fixture(scope="function")
async def valid_refresh_token(db_session: AsyncSession, test_user: User) -> str:
    """
    Create a valid refresh token for the test user.

    This fixture creates a refresh token, stores it in the database, and
    returns the token string. Use this for testing the token refresh endpoint.
    """
    token_str = create_refresh_token(subject=str(test_user.id))

    refresh_token = RefreshToken(
        id=uuid4(),
        token=token_str,
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        revoked=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(refresh_token)
    await db_session.commit()

    return token_str


@pytest_asyncio.fixture(scope="function")
async def revoked_refresh_token(db_session: AsyncSession, test_user: User) -> str:
    """
    Create a revoked refresh token for the test user.

    This fixture creates a refresh token that has been revoked, which should
    be rejected when used with the refresh endpoint.
    """
    token_str = create_refresh_token(subject=str(test_user.id))

    refresh_token = RefreshToken(
        id=uuid4(),
        token=token_str,
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        revoked=True,  # This token is revoked
        revoked_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(refresh_token)
    await db_session.commit()

    return token_str


@pytest_asyncio.fixture(scope="function")
async def expired_refresh_token(db_session: AsyncSession, test_user: User) -> str:
    """
    Create an expired refresh token for the test user.

    This fixture creates a refresh token that has already expired, which should
    be rejected when used with the refresh endpoint.
    """
    token_str = create_refresh_token(
        subject=str(test_user.id),
        expires_delta=timedelta(days=-1),  # Expired 1 day ago
    )

    refresh_token = RefreshToken(
        id=uuid4(),
        token=token_str,
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Already expired
        revoked=False,
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    db_session.add(refresh_token)
    await db_session.commit()

    return token_str


# Helper function fixtures

@pytest.fixture
def create_test_user_data() -> dict:
    """
    Generate test data for user registration.

    Returns a dictionary with valid user registration data that can be
    modified for specific test cases.
    """
    return {
        "email": f"newuser_{uuid4().hex[:8]}@example.com",
        "password": "securepassword123",
        "full_name": "New Test User",
    }


@pytest.fixture
def login_data() -> dict:
    """
    Generate test data for user login.

    Returns the default login credentials matching the test_user fixture.
    """
    return {
        "username": "test@example.com",  # OAuth2 form uses 'username' for email
        "password": "testpassword123",
    }
