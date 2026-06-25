"""pytest fixtures shared across all tests.

Test database strategy (D-16, D-17, D-18):
  - Real ephemeral mysql:8.4 container spun up once per test session via testcontainers.
  - Schema built by `alembic upgrade head` against the test DB — verifies migrations work.
  - Each test gets transaction-level isolation: a nested transaction is opened, the test
    runs, then the transaction is rolled back — DB stays clean between tests.

FastAPI dependency override pattern:
  - `get_db` from `app.core.dependencies` is overridden via `app.dependency_overrides`
    to inject the transactional test session.
  - This is the FastAPI-recommended approach — no monkey-patching needed.

Requirements:
  - Docker must be running locally for testcontainers to spin up the MySQL container.
  - `testcontainers[mysql]>=4.0.0` must be in dev dependencies.
"""

import os
import subprocess

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.mysql import MySqlContainer

from app.core.dependencies import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Session-scoped: real MySQL container + alembic-built schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mysql_container():
    """Spin up a real mysql:8.4 container once per test session (D-16)."""
    with MySqlContainer("mysql:8.4") as container:
        yield container


@pytest.fixture(scope="session")
def test_database_url(mysql_container: MySqlContainer) -> str:
    """Build an asyncmy DSN from the testcontainer's exposed connection details."""
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    user = mysql_container.username
    password = mysql_container.password
    database = mysql_container.dbname
    return f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


@pytest.fixture(scope="session")
def run_migrations(test_database_url: str) -> None:
    """Run `alembic upgrade head` against the test DB (D-17).

    This verifies that the migration scripts are correct and produces an
    identical schema to production — not `metadata.create_all()`.
    """
    env = {**os.environ, "DATABASE_URL": test_database_url}
    subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_database_url: str, run_migrations: None):
    """Async engine connected to the test MySQL container."""
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Function-scoped: per-test transaction rollback for isolation (D-18)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session(test_engine) -> AsyncSession:
    """Per-test AsyncSession with transaction rollback for isolation (D-18).

    Opens a connection + outer transaction, binds a session to it, yields the
    session to the test, then rolls back — leaving the DB pristine for the next
    test without touching the real MySQL container data.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as sess:
            yield sess
        await conn.rollback()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    """AsyncClient with the test DB session injected via dependency override.

    Overrides `get_db` (the dependency the router chain resolves through) so
    every request during the test uses the transactional test session.
    """

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth fixtures — function-scoped; reuse the client fixture (Phase 3)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def registered_user(client: httpx.AsyncClient) -> dict:
    """Create a test user via POST /auth/register and return the response body."""
    resp = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 201, f"Register failed: {resp.json()}"
    return resp.json()


@pytest_asyncio.fixture
async def auth_client(client: httpx.AsyncClient, registered_user: dict) -> httpx.AsyncClient:
    """AsyncClient pre-authenticated with the registered user's access token."""
    resp = await client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
