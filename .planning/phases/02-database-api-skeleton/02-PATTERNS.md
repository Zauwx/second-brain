# Phase 2: Database + API Skeleton - Pattern Map

**Mapped:** 2026-06-24
**Files analyzed:** 14 new/modified files
**Analogs found:** 9 / 14 (5 have no codebase analog — use STACK.md reference patterns)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/notes/router.py` | router | request-response (CRUD) | `app/api/health.py` | role-match |
| `app/notes/schemas.py` | schema/model | transform | `app/core/config.py` | partial (Pydantic v2 pattern) |
| `app/notes/models.py` | model (ORM) | CRUD | none in codebase | no analog |
| `app/notes/service.py` | service | CRUD | none in codebase | no analog |
| `app/notes/repository.py` | repository | CRUD | none in codebase | no analog |
| `app/core/database.py` | utility/config | CRUD | `app/core/config.py` | partial (core singleton pattern) |
| `alembic/env.py` | config (migration) | batch | none in codebase | no analog |
| `alembic/versions/<first>.py` | migration | batch | none in codebase | no analog |
| `tests/conftest.py` | test fixture | request-response | `tests/test_health.py` | partial (AsyncClient pattern) |
| `tests/test_notes.py` | test | request-response | `tests/test_health.py` | role-match |
| `app/main.py` | config (modified) | request-response | `app/main.py` (self) | exact (extension) |
| `app/core/config.py` | config (modified) | request-response | `app/core/config.py` (self) | exact (extension) |
| `docker-compose.yml` | config (modified) | — | `docker-compose.yml` (self) | exact (extension) |
| `pyproject.toml` | config (modified) | — | `pyproject.toml` (self) | exact (extension) |

---

## Pattern Assignments

### `app/notes/router.py` (router, request-response/CRUD)

**Analog:** `app/api/health.py`

**Imports pattern** (health.py lines 1-3 — extend this):
```python
from fastapi import APIRouter

router = APIRouter()
```

**Extended imports for notes router:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.notes.schemas import NoteCreate, NoteRead, NoteUpdate, NoteListResponse
from app.notes.service import NoteService
```

**Core route pattern** (health.py lines 6-9 — mirror structure, extend for CRUD):
```python
@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint — smoke test for 'the service is reachable'."""
    return {"status": "ok"}
```

Notes router follows the same `APIRouter` + `async def` shape. Every handler has zero business logic — it calls the service and returns the result. Status codes per D-09: 200 list/read/update, 201 create, 204 delete, 404 not found, 422 validation.

**Route signatures to implement:**
```python
router = APIRouter(prefix="/notes", tags=["notes"])

@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(body: NoteCreate, session: AsyncSession = Depends(get_session)) -> NoteRead:
    ...

@router.get("/", response_model=NoteListResponse)
async def list_notes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at"),
    filter: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> NoteListResponse:
    ...

@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, session: AsyncSession = Depends(get_session)) -> NoteRead:
    ...

@router.put("/{note_id}", response_model=NoteRead)
async def update_note(note_id: int, body: NoteUpdate, session: AsyncSession = Depends(get_session)) -> NoteRead:
    ...

@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, session: AsyncSession = Depends(get_session)) -> None:
    ...
```

**Error handling pattern** — use FastAPI's built-in `HTTPException` (D-19, no custom envelope):
```python
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
```

The `size > 100` case is enforced automatically by `Query(..., le=100)` which produces a 422 response with FastAPI's standard validation body — no explicit check needed.

---

### `app/notes/schemas.py` (schema, transform)

**Analog:** `app/core/config.py` (Pydantic v2 `model_config` pattern, lines 1-19)

**Pydantic v2 `SettingsConfigDict` import pattern** (config.py lines 1-2):
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
```

For schemas, replace with standard Pydantic v2:
```python
from pydantic import BaseModel, ConfigDict
```

**Core schema pattern** — three separate schemas per domain (D-13):
```python
class NoteCreate(BaseModel):
    """Fields required to create a new note."""
    content: str
    source_url: str | None = None

class NoteUpdate(BaseModel):
    """All fields optional for partial update (PATCH semantics via PUT)."""
    content: str | None = None
    source_url: str | None = None

class NoteRead(BaseModel):
    """Response schema — maps ORM model to JSON. Requires from_attributes=True."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    source_url: str | None
    created_at: datetime
    updated_at: datetime

class NoteListResponse(BaseModel):
    """Pagination envelope per D-06: {items, total, page, size, pages}."""
    items: list[NoteRead]
    total: int
    page: int
    size: int
    pages: int
```

`model_config = ConfigDict(from_attributes=True)` is mandatory on `NoteRead` so that SQLAlchemy ORM instances serialize correctly (STACK.md, CLAUDE.md constraint).

---

### `app/notes/models.py` (ORM model, CRUD)

**Analog:** None in codebase. Use STACK.md + CLAUDE.md patterns directly.

**Pattern from STACK.md (SQLAlchemy 2.x, DeclarativeBase, NOT legacy `declarative_base()`):**
```python
from sqlalchemy import BigInteger, Text, String, DateTime, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_notes_created_at", "created_at"),  # supports sort-by-created_at
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
```

Key constraints from decisions:
- D-01: BIGINT autoincrement PK
- D-02: `content` (TEXT, required) + `source_url` (VARCHAR 2048, nullable) — no `title`
- D-03: `created_at` + `updated_at`, server-managed via `server_default=func.now()` and `onupdate=func.now()`
- D-15: `Base` is imported from `app.core.database`, not declared here
- Table-level `mysql_charset="utf8mb4"` is required for Alembic to emit the correct DDL

---

### `app/notes/service.py` (service, CRUD)

**Analog:** None in codebase. Mirror the architecture pattern from ARCHITECTURE.md Pattern 3.

**Core service pattern:**
```python
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteUpdate, NoteListResponse, NoteRead
from app.notes.models import Note

class NoteService:
    def __init__(self, repository: NoteRepository) -> None:
        self._repo = repository

    async def create(self, data: NoteCreate) -> Note:
        return await self._repo.create(data)

    async def get_or_404(self, note_id: int) -> Note:
        note = await self._repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(status_code=404, detail="Note not found")
        return note

    async def list_notes(
        self, page: int, size: int, sort: str, filter: str | None
    ) -> NoteListResponse:
        items, total = await self._repo.list_paginated(page, size, sort, filter)
        pages = (total + size - 1) // size
        return NoteListResponse(items=items, total=total, page=page, size=size, pages=pages)

    async def update(self, note_id: int, data: NoteUpdate) -> Note:
        note = await self.get_or_404(note_id)
        return await self._repo.update(note, data)

    async def delete(self, note_id: int) -> None:
        note = await self.get_or_404(note_id)
        await self._repo.delete(note)
```

Service is a plain Python class — no HTTP concepts, no `AsyncSession` directly (session lives in the repository). The router instantiates `NoteService(NoteRepository(session))` in the handler signature or via a `Depends()` helper.

---

### `app/notes/repository.py` (repository, CRUD)

**Analog:** None in codebase. Use ARCHITECTURE.md Pattern 3 + STACK.md async SQLAlchemy pattern.

**Imports + constructor pattern:**
```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc, desc

from app.notes.models import Note
from app.notes.schemas import NoteCreate, NoteUpdate

class NoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

**CRUD operation pattern** (all SQL lives here, nowhere else):
```python
    async def create(self, data: NoteCreate) -> Note:
        note = Note(content=data.content, source_url=data.source_url)
        self._session.add(note)
        await self._session.commit()
        await self._session.refresh(note)
        return note

    async def get_by_id(self, note_id: int) -> Note | None:
        result = await self._session.execute(
            select(Note).where(Note.id == note_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self, page: int, size: int, sort: str, filter: str | None
    ) -> tuple[list[Note], int]:
        # Build base query with optional LIKE filter (D-08)
        query = select(Note)
        if filter:
            query = query.where(Note.content.ilike(f"%{filter}%"))
        
        # Count total (D-06 envelope)
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_q)).scalar_one()
        
        # Apply sort (D-07: leading '-' = desc)
        order_col = Note.created_at if "created_at" in sort else Note.updated_at
        order_fn = desc if sort.startswith("-") else asc
        query = query.order_by(order_fn(order_col))
        
        # Apply pagination
        query = query.offset((page - 1) * size).limit(size)
        result = await self._session.execute(query)
        return list(result.scalars().all()), total

    async def update(self, note: Note, data: NoteUpdate) -> Note:
        if data.content is not None:
            note.content = data.content
        if data.source_url is not None:
            note.source_url = data.source_url
        await self._session.commit()
        await self._session.refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        await self._session.delete(note)
        await self._session.commit()
```

---

### `app/core/database.py` (utility, CRUD)

**Analog:** `app/core/config.py` — same "core singleton" pattern (module-level instance, imported everywhere)

**Config singleton pattern to mirror** (config.py lines 1-19):
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    log_level: str = "INFO"

settings = Settings()   # <-- module-level singleton
```

**Database.py full pattern** (STACK.md async engine section):
```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models. Import this into each domain's models.py."""
    pass


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,   # recover from stale connections after MySQL restart
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
# expire_on_commit=False prevents lazy-load errors in async context (STACK.md pitfall)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields one AsyncSession per request, closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session
```

The `engine` and `AsyncSessionLocal` are module-level singletons (same pattern as `settings` in config.py). `engine.dispose()` must be called in the FastAPI lifespan shutdown.

---

### `app/main.py` (modified — router registration + lifespan)

**Analog:** `app/main.py` itself (current state, lines 1-12 — extend, do not replace)

**Current state** (main.py lines 1-12):
```python
from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Second Brain",
    description="Self-hosted second brain: save notes, organize with tags, query in natural language",
    version="0.1.0",
)

app.include_router(health_router)
```

**Required additions** — add lifespan + notes router registration:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.health import router as health_router
from app.notes.router import router as notes_router
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: connection pool is created lazily by SQLAlchemy — nothing to do
    yield
    # shutdown: dispose engine, close all pooled connections cleanly
    await engine.dispose()


app = FastAPI(
    title="Second Brain",
    description="Self-hosted second brain: save notes, organize with tags, query in natural language",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(notes_router)
```

Use `lifespan=` parameter, not the deprecated `on_startup` / `on_shutdown` (STACK.md explicit guidance).

---

### `app/core/config.py` (modified — add DATABASE_URL + sort field validation)

**Analog:** `app/core/config.py` itself (current state, lines 1-19 — extend)

**Current state** (config.py lines 1-19):
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    log_level: str = "INFO"

settings = Settings()
```

**Add `database_url` field** (already present in `.env.example` line 34):
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str  # required — no default, must be set in .env
```

The `extra="ignore"` already handles all the Phase 3+ vars (JWT, Anthropic, Ollama) without errors. No further changes needed to config structure.

---

### `alembic/env.py` (new — async Alembic env)

**Analog:** None in codebase. Use STACK.md async env.py pattern exactly.

**Full async env.py pattern** (STACK.md lines 99-116):
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.core.database import Base
# Import all domain models so Alembic autogenerate detects their tables:
from app.notes import models as _notes_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,   # no pooling in migration runs
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    # Offline mode: generate SQL script without DB connection
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
```

Critical: `NullPool` is mandatory in migration runs to avoid connection reuse issues. Import all domain models before `target_metadata = Base.metadata` or autogenerate will miss tables.

---

### `alembic/versions/<timestamp>_create_notes_table.py` (new — first migration)

**Analog:** None in codebase.

**Migration must produce utf8mb4 DDL** (D-15, CLAUDE.md). Autogenerate from the `Note` model with `__table_args__ = {"mysql_charset": "utf8mb4", ...}` will do this correctly. Key DDL the migration must emit:

```sql
CREATE TABLE notes (
    id BIGINT NOT NULL AUTO_INCREMENT,
    content TEXT NOT NULL,
    source_url VARCHAR(2048),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_notes_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Do NOT use `Base.metadata.create_all()` anywhere in application code (D-15 hard requirement).

---

### `tests/conftest.py` (new — testcontainers + async fixtures)

**Analog:** `tests/test_health.py` (partial — same `ASGITransport` / `AsyncClient` pattern, lines 1-20)

**Current test pattern to extend** (test_health.py lines 1-20):
```python
import httpx
import pytest
from httpx import ASGITransport

from app.main import app

@pytest.mark.asyncio
async def test_health_returns_200_and_ok_body() -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Conftest structure** — session-scoped container + transaction-per-test isolation (D-16, D-17, D-18):
```python
import asyncio
import subprocess
import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from testcontainers.mysql import MySqlContainer

from app.main import app
from app.core import database as db_module
from app.core.database import Base


@pytest.fixture(scope="session")
def mysql_container():
    """Spin up a real mysql:8.4 container once per test session."""
    with MySqlContainer("mysql:8.4") as container:
        yield container


@pytest.fixture(scope="session")
def test_database_url(mysql_container) -> str:
    host = mysql_container.get_container_host_ip()
    port = mysql_container.get_exposed_port(3306)
    user = mysql_container.username
    password = mysql_container.password
    database = mysql_container.dbname
    return f"mysql+asyncmy://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


@pytest.fixture(scope="session")
def run_migrations(test_database_url: str) -> None:
    """Run alembic upgrade head against the test DB — verifies migrations work (D-17)."""
    import os
    env = {**os.environ, "DATABASE_URL": test_database_url}
    subprocess.run(["alembic", "upgrade", "head"], env=env, check=True)


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_database_url: str, run_migrations):
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_engine) -> AsyncSession:
    """Per-test async session with transaction rollback for isolation (D-18)."""
    async with test_engine.begin() as conn:
        async with async_sessionmaker(bind=conn, expire_on_commit=False)() as sess:
            yield sess
            await conn.rollback()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> httpx.AsyncClient:
    """AsyncClient with the test DB session injected via dependency_override."""
    from app.core.database import get_session

    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

Note: `asyncio_mode = "auto"` is already set in `pyproject.toml` (line 58) — the `@pytest.mark.asyncio` decorator is not needed on individual tests.

---

### `tests/test_notes.py` (new — CRUD endpoint tests)

**Analog:** `tests/test_health.py` (exact pattern — same `client` fixture, same assert style)

**Pattern to follow** (test_health.py lines 8-20):
```python
@pytest.mark.asyncio
async def test_health_returns_200_and_ok_body() -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Notes test pattern** — use the `client` fixture from conftest (no inline `AsyncClient` setup):
```python
async def test_create_note_returns_201(client: httpx.AsyncClient) -> None:
    response = await client.post("/notes/", json={"content": "test note"})
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "test note"
    assert "id" in data
    assert "created_at" in data

async def test_get_note_returns_404_when_missing(client: httpx.AsyncClient) -> None:
    response = await client.get("/notes/999999")
    assert response.status_code == 404

async def test_list_notes_returns_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/notes/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data

async def test_list_notes_rejects_oversized_page(client: httpx.AsyncClient) -> None:
    response = await client.get("/notes/?size=101")
    assert response.status_code == 422
```

---

### `docker-compose.yml` (modified — add mysql:8.4 service)

**Analog:** `docker-compose.yml` itself (current state, lines 1-23 — extend)

**Current state** (docker-compose.yml lines 13-23):
```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

**Add mysql service and wire depends_on** (D-20):
```yaml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    depends_on:
      mysql:
        condition: service_healthy  # api waits for mysql healthcheck to pass

  mysql:
    image: mysql:8.4
    env_file:
      - .env                         # provides MYSQL_ROOT_PASSWORD, MYSQL_USER, etc.
    volumes:
      - mysql_data:/var/lib/mysql    # persist data across container restarts
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p$$MYSQL_ROOT_PASSWORD"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    # NO ports: block — mysql stays on internal Docker network (D-20)

networks:
  default:
    name: second-brain-backend

volumes:
  mysql_data:
```

The `$$MYSQL_ROOT_PASSWORD` double-dollar escapes the `$` in Docker Compose so it reads the env var at runtime rather than shell-expanding it at parse time.

---

### `pyproject.toml` (modified — add runtime + dev dependencies)

**Analog:** `pyproject.toml` itself (current state, lines 1-59 — extend dependency blocks only)

**Current dependencies** (pyproject.toml lines 6-18):
```toml
dependencies = [
    "fastapi>=0.115.0,<0.116.0",
    "uvicorn[standard]>=0.32.0,<0.33.0",
    "pydantic-settings>=2.0.0,<3.0.0",
]

[dependency-groups]
dev = [
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.0",
]
```

**Add to `dependencies`:**
```toml
"sqlalchemy>=2.0.0,<3.0.0",
"asyncmy>=0.2.0,<0.3.0",
"alembic>=1.14.0,<2.0.0",
```

**Add to `[dependency-groups] dev`:**
```toml
"testcontainers[mysql]>=4.0.0",
```

The `testcontainers[mysql]` extra includes the MySQL-specific container class. Exact version pinning follows the `>=X.Y.0,<(X+1).0.0` semver-range convention already established in the file.

---

## Shared Patterns

### FastAPI Dependency Injection (DI)
**Source:** STACK.md + ARCHITECTURE.md Pattern 1
**Apply to:** `app/notes/router.py`, `tests/conftest.py`

Every route receives an `AsyncSession` via `Depends(get_session)`. The session is yielded by `get_session()` in `app/core/database.py`. In tests, `dependency_overrides[get_session]` replaces it with the transactional test session. This pattern is the foundation for all future domains.

```python
# In router handler signature:
session: AsyncSession = Depends(get_session)

# In conftest override:
app.dependency_overrides[get_session] = override_get_session
```

### Pydantic v2 `from_attributes=True` ORM Mode
**Source:** CLAUDE.md + STACK.md
**Apply to:** `app/notes/schemas.py` (NoteRead), and all future `*Read` schemas

```python
from pydantic import BaseModel, ConfigDict

class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # ... fields
```

Do NOT use `class Config: orm_mode = True` (Pydantic v1 syntax — banned per CLAUDE.md).

### `expire_on_commit=False` on AsyncSessionLocal
**Source:** STACK.md
**Apply to:** `app/core/database.py`, `tests/conftest.py`

```python
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

Required to avoid lazy-load errors when accessing ORM attributes after `await session.commit()` in async context.

### `DeclarativeBase` (not `declarative_base()`)
**Source:** CLAUDE.md "What NOT to Use" + STACK.md
**Apply to:** `app/core/database.py`

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

`declarative_base()` is the legacy SQLAlchemy 1.x API. Using `DeclarativeBase` is required per CLAUDE.md.

### mysql_charset Table Args
**Source:** CLAUDE.md + ARCHITECTURE.md MySQL Schema section
**Apply to:** `app/notes/models.py`, all future ORM models

```python
__table_args__ = (
    # ... indexes ...,
    {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
)
```

Without this, Alembic emits DDL without charset — MySQL defaults to `latin1` in some configurations, breaking emoji/multilingual content.

### Error Handling — FastAPI Defaults (D-19)
**Source:** D-19 decision, `app/api/health.py` (no custom error handling — same applies to notes)
**Apply to:** `app/notes/router.py`, `app/notes/service.py`

Use `HTTPException` for 404. Let FastAPI's built-in RequestValidationError handler produce 422. No custom error envelope this phase.

```python
from fastapi import HTTPException, status
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
```

### asyncio_mode = "auto" Already Set
**Source:** `pyproject.toml` lines 57-59
**Apply to:** `tests/test_notes.py`, `tests/conftest.py`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Do NOT add `@pytest.mark.asyncio` to individual test functions — it's already global. Do NOT add `@pytest.fixture(loop_scope=...)` — the default event loop scope is fine for these tests.

---

## No Analog Found

Files with no close match in the codebase (planner should use STACK.md + ARCHITECTURE.md patterns):

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/notes/models.py` | ORM model | CRUD | No ORM models exist yet — first SQLAlchemy model in the project |
| `app/notes/service.py` | service | CRUD | No service layer exists yet — first service class in the project |
| `app/notes/repository.py` | repository | CRUD | No repositories exist yet — first repository class in the project |
| `alembic/env.py` | migration config | batch | No Alembic setup exists yet — async env.py must be written from scratch |
| `alembic/versions/*.py` | migration | batch | No migration files exist yet — first migration |

For these five files, the planner should reference:
- STACK.md "MySQL + SQLAlchemy 2: Async Pattern" (engine, sessionmaker, get_db)
- STACK.md "Alembic: Async env.py" (async migration runner)
- ARCHITECTURE.md "Pattern 3: Repository — No Raw SQL in Services"
- CLAUDE.md "What NOT to Use" (DeclarativeBase, asyncmy not aiomysql, no passlib)

---

## Metadata

**Analog search scope:** `app/`, `tests/`, `docker/`, project root config files
**Files scanned:** 9 source files (all Python files in the project at this stage)
**Pattern extraction date:** 2026-06-24

**Key observations:**
- The codebase is at Phase 1 skeleton — only health endpoint, config, and main exist. All domain patterns (models, services, repositories) are net-new.
- The `app/notes/` and `app/services/` and `app/repositories/` package stubs exist as empty `__init__.py` directories. D-11 requires removing `app/services/` and `app/repositories/` — they are placeholders superseded by domain-per-folder.
- `asyncio_mode = "auto"` is already configured in pyproject.toml — no test decorator boilerplate needed.
- The `.env.example` already contains `DATABASE_URL` with the correct `mysql+asyncmy://` DSN shape (line 34) — `app/core/config.py` just needs a `database_url: str` field to consume it.
- `docker-compose.yml` is minimal (api only) — mysql service is a clean addition with no conflicts.
