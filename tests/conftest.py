"""pytest fixtures shared across all tests.

Test database strategy:
  - Uses SQLite in-memory via aiosqlite for fast, dependency-free tests.
  - SQLite is API-compatible with MySQL for CRUD operations (different from
    MySQL for FULLTEXT, JSON columns, etc. — those are tested in Docker in CI).
  - `Base.metadata.create_all()` creates tables without Alembic — tests don't
    need migration history, only the schema.
  - Each test gets a fresh engine + tables via function-scoped fixtures.

FastAPI dependency override pattern:
  - `get_db` is overridden via `app.dependency_overrides` to inject the test
    SQLite session instead of the production MySQL session.
  - This is the FastAPI-recommended approach — no monkey-patching needed.

Why SQLite for tests:
  - No external service required → tests run anywhere (CI, dev machine, Docker).
  - The actual MySQL integration is validated by `alembic upgrade head` in Docker.
  - SQLite limitations (no FULLTEXT, no UNSIGNED INT enforcement) are acceptable
    because Phase 2 tests only cover basic CRUD, not search or constraints.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.dependencies import get_db
from app.database import Base
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite engine (per test session, tables created per test)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def test_engine():
    """Create a fresh async SQLite engine for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a test AsyncSession backed by the in-memory SQLite engine."""
    test_session_local = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with test_session_local() as session:
        yield session


@pytest_asyncio.fixture()
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an httpx AsyncClient with the test DB injected via dependency override.

    The `get_db` dependency is replaced so every request during the test uses
    the same in-memory SQLite session — no MySQL required.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
