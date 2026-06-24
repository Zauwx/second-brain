"""Async database engine, session factory, and ORM base class.

All ORM models import `Base` from here.
The FastAPI dependency `get_db` (in app/core/dependencies.py) yields an AsyncSession
per request and closes it cleanly on response completion.

Design notes:
- `create_async_engine` uses asyncmy (not aiomysql — unmaintained since 2021).
- `expire_on_commit=False` prevents lazy-load errors after commit in async context.
- `pool_pre_ping=True` detects stale connections after MySQL restart.
- DSN is read lazily from Settings so tests can override via dependency injection.
"""

from collections.abc import AsyncGenerator  # noqa: F401 — re-exported for downstream use

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Every model in this project inherits from this class so that
    Alembic can auto-detect table changes via `Base.metadata`.
    """


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,  # verify connection before checkout (handles MySQL restart)
    pool_size=10,
    max_overflow=20,
    echo=False,  # set to True temporarily to log SQL during development
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,  # avoid lazy-load errors in async context after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession and ensures clean teardown.

    Usage in a router:
        @router.get("/resource")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
