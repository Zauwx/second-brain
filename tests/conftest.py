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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.mysql import MySqlContainer

from app.core.dependencies import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Session-scoped: real MySQL container + alembic-built schema
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mysql_container():
    """Spin up mysql:8.4 with innodb_ft_min_token_size=2 for 2-char FULLTEXT tests (D-11)."""
    container = MySqlContainer("mysql:8.4").with_command("--innodb-ft-min-token-size=2")
    with container:
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


@pytest_asyncio.fixture
async def user_a_client(session: AsyncSession) -> AsyncClient:
    """Authenticated AsyncClient for user A (a@example.com) — cross-user isolation tests.

    Creates a SEPARATE AsyncClient (not sharing headers with the `client` fixture) so
    user A and user B can hold independent Authorization headers simultaneously.
    The same get_db override session is used so both clients share the transaction
    that will be rolled back at teardown (Pitfall 8 — dependency_overrides.clear() runs).
    """

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register user A
        reg = await ac.post(
            "/auth/register",
            json={"email": "a@example.com", "password": "Test1234!"},
        )
        assert reg.status_code == 201, f"user_a register failed: {reg.json()}"

        # Login as user A
        login = await ac.post(
            "/auth/login",
            json={"email": "a@example.com", "password": "Test1234!"},
        )
        assert login.status_code == 200, f"user_a login failed: {login.json()}"
        ac.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# FULLTEXT-committed fixtures (function-scoped, real commits + explicit cleanup)
#
# MySQL InnoDB FULLTEXT indexes only see COMMITTED data. The standard `session`
# fixture uses transaction rollback (no real commit), so FULLTEXT queries return
# zero results even for freshly inserted rows. These fixtures use the engine
# directly (no outer transaction) so each `session.commit()` in route handlers
# is a real DB commit visible to FULLTEXT queries.
#
# Cleanup: after each test, DELETE FROM users cascades to notes/tags/collections
# and all junction table rows — leaving the DB clean for the next test.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def ft_session(test_engine) -> AsyncSession:
    """Per-test committed session for FULLTEXT search tests.

    Creates a fresh session from the engine (not bound to an outer transaction),
    so NoteRepository.create() commits real transactions that InnoDB's FULLTEXT
    index can see.  Deletes all user-owned data on teardown via CASCADE.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as sess:
        yield sess
        # CASCADE: users → notes → note_tags/note_collections; users → tags/collections
        await sess.execute(text("DELETE FROM users"))
        await sess.commit()


@pytest_asyncio.fixture
async def ft_client(ft_session: AsyncSession) -> AsyncClient:
    """AsyncClient backed by a committed session — for FULLTEXT search tests."""

    async def override_get_db() -> AsyncSession:  # type: ignore[misc]
        yield ft_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def ft_auth_client(ft_client: httpx.AsyncClient) -> httpx.AsyncClient:
    """Pre-authenticated AsyncClient for FULLTEXT search tests.

    Uses ft_client (committed session) so inserted notes are visible to FULLTEXT.
    """
    resp = await ft_client.post(
        "/auth/register",
        json={"email": "ft@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 201, f"ft register failed: {resp.json()}"
    resp = await ft_client.post(
        "/auth/login",
        json={"email": "ft@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 200, f"ft login failed: {resp.json()}"
    token = resp.json()["access_token"]
    ft_client.headers["Authorization"] = f"Bearer {token}"
    return ft_client


@pytest_asyncio.fixture
async def user_b_client(session: AsyncSession) -> AsyncClient:
    """Authenticated AsyncClient for user B (b@example.com) — cross-user isolation tests.

    Creates a SEPARATE AsyncClient from user_a_client so each user holds their own
    Authorization header. Both fixtures share the same `session` transaction (rolled back
    at teardown).

    NOTE: When used together with user_a_client in the same test, the second fixture's
    dependency_overrides.clear() at teardown clears the override set by both fixtures.
    This is safe because both fixtures set the same override (same session).
    """

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register user B
        reg = await ac.post(
            "/auth/register",
            json={"email": "b@example.com", "password": "Test1234!"},
        )
        assert reg.status_code == 201, f"user_b register failed: {reg.json()}"

        # Login as user B
        login = await ac.post(
            "/auth/login",
            json={"email": "b@example.com", "password": "Test1234!"},
        )
        assert login.status_code == 200, f"user_b login failed: {login.json()}"
        ac.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield ac

    app.dependency_overrides.clear()
