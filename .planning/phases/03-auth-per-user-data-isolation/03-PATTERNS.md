# Phase 3: Auth + Per-User Data Isolation - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 18 new/modified files
**Analogs found:** 18 / 18

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/auth/__init__.py` | config | — | `app/notes/__init__.py` | exact |
| `app/auth/models.py` | model | CRUD | `app/notes/models.py` | exact |
| `app/auth/schemas.py` | model | request-response | `app/notes/schemas.py` | exact |
| `app/auth/repository.py` | service | CRUD | `app/notes/repository.py` | exact |
| `app/auth/service.py` | service | request-response | `app/notes/service.py` | exact |
| `app/auth/router.py` | controller | request-response | `app/notes/router.py` | exact |
| `app/core/dependencies.py` | middleware | request-response | `app/core/dependencies.py` (existing) | exact |
| `app/core/config.py` | config | — | `app/core/config.py` (existing) | exact |
| `app/main.py` | config | — | `app/main.py` (existing) | exact |
| `app/notes/models.py` | model | CRUD | `app/notes/models.py` (existing) | exact |
| `app/notes/repository.py` | service | CRUD | `app/notes/repository.py` (existing) | exact |
| `app/notes/service.py` | service | request-response | `app/notes/service.py` (existing) | exact |
| `app/notes/router.py` | controller | request-response | `app/notes/router.py` (existing) | exact |
| `app/notes/schemas.py` | model | request-response | `app/notes/schemas.py` (existing) | exact |
| `alembic/env.py` | config | — | `alembic/env.py` (existing) | exact |
| `alembic/versions/XXXX_create_users_and_refresh_tokens.py` | migration | CRUD | `alembic/versions/d51191e92276_create_notes_table.py` | exact |
| `alembic/versions/YYYY_add_user_id_to_notes.py` | migration | CRUD | `alembic/versions/d51191e92276_create_notes_table.py` | role-match |
| `tests/conftest.py` | test | request-response | `tests/conftest.py` (existing) | exact |
| `tests/test_auth.py` | test | request-response | `tests/test_notes_crud.py` | exact |
| `tests/test_notes_isolation.py` | test | request-response | `tests/test_notes_crud.py` | role-match |
| `tests/test_notes_crud.py` | test | request-response | `tests/test_notes_crud.py` (existing) | exact |
| `tests/test_notes_list.py` | test | request-response | `tests/test_notes_list.py` (existing) | exact |

---

## Pattern Assignments

### `app/auth/__init__.py` (config)

**Analog:** `app/notes/__init__.py`

Empty file — copy verbatim. No contents needed; presence marks the directory as a Python package.

---

### `app/auth/models.py` (model, CRUD)

**Analog:** `app/notes/models.py`

**Imports pattern** (`app/notes/models.py` lines 17-21):
```python
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
```

**Table args pattern** (`app/notes/models.py` lines 28-33) — copy this block verbatim for every new model:
```python
__table_args__ = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}
```

**PK column pattern** (`app/notes/models.py` lines 35-37) — BIGINT unsigned PK, autoincrement:
```python
id: Mapped[int] = mapped_column(
    INTEGER(unsigned=True), primary_key=True, autoincrement=True
)
```

**Timestamp columns pattern** (`app/notes/models.py` lines 49-59) — server-managed, no Python default:
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    server_default=func.now(),
)
updated_at: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    server_default=func.now(),
    onupdate=func.now(),
)
```

**New imports required for `auth/models.py`** beyond the notes analog:
```python
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import relationship
```

`User` adds: `email` (String(255) unique), `hashed_password` (String(255)), and `relationship` back-refs to `Note` and `RefreshToken`.
`RefreshToken` adds: `jti` (String(36) unique indexed), `user_id` FK (`INTEGER(unsigned=True)`, `ForeignKey("users.id", ondelete="CASCADE")`), `expires_at` (DateTime), `revoked` (Boolean default False), `revoked_at` (DateTime nullable).

---

### `app/auth/schemas.py` (model, request-response)

**Analog:** `app/notes/schemas.py`

**Three-schema pattern** (`app/notes/schemas.py` lines 1-11) — the file-level docstring explains the pattern; copy the pattern for auth:
- `UserCreate` (register request body) — analogous to `NoteCreate`
- `UserRead` (register + profile response) — analogous to `NoteRead` with `from_attributes=True`
- `LoginRequest` (login body) — analogous to `NoteCreate`
- `TokenResponse` (login/refresh response) — new shape, no analog; use research
- `RefreshRequest` / `LogoutRequest` (body carrying `refresh_token`) — simple single-field models

**from_attributes pattern** (`app/notes/schemas.py` lines 62-68):
```python
class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    source_url: str | None
    created_at: datetime
    updated_at: datetime
```
`UserRead` follows the same shape: `model_config = ConfigDict(from_attributes=True)`, then `id`, `email`, `created_at`.

**Field with validation pattern** (`app/notes/schemas.py` lines 22-35) — `Field(min_length=1, description=...)` is the local idiom:
```python
content: str = Field(
    min_length=1,
    description="Main note content (required)",
)
```
For `UserCreate.password`, replace `Field` with a `@field_validator` (from RESEARCH.md Pattern in Code Examples section).

**New imports needed** beyond the notes analog:
```python
from pydantic import EmailStr, field_validator
import re
```

---

### `app/auth/repository.py` (service, CRUD)

**Analog:** `app/notes/repository.py`

**Class + constructor pattern** (`app/notes/repository.py` lines 27-31):
```python
class NoteRepository:
    """Data-access layer for Note records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```
`AuthRepository.__init__` is identical in shape: `self._session = session`.

**Insert + refresh pattern** (`app/notes/repository.py` lines 33-43):
```python
async def create(self, data: NoteCreate) -> Note:
    """Insert a new Note row and return the persisted model instance."""
    note = Note(
        title=data.title,
        content=data.content,
        source_url=data.source_url,
    )
    self._session.add(note)
    await self._session.commit()
    await self._session.refresh(note)
    return note
```
`create_user` and `create_refresh_token` follow this identical pattern: construct the ORM instance, `session.add()`, `commit()`, `refresh()`, return.

**Scalar query pattern** (`app/notes/repository.py` lines 45-48):
```python
async def get_by_id(self, note_id: int) -> Note | None:
    result = await self._session.execute(select(Note).where(Note.id == note_id))
    return result.scalar_one_or_none()
```
`get_user_by_email`, `get_refresh_token_by_jti` both follow the same `select(...).where(...)` → `scalar_one_or_none()` pattern.

**Update-in-place pattern** (`app/notes/repository.py` lines 103-113):
```python
async def update(self, note: Note, data: NoteUpdate) -> Note:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    await self._session.commit()
    await self._session.refresh(note)
    return note
```
`revoke_refresh_token` uses this same `setattr` + `commit` + `refresh` pattern to flip `revoked = True` and set `revoked_at`.

**Imports pattern** (`app/notes/repository.py` lines 12-17):
```python
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.notes.models import Note
from app.notes.schemas import NoteCreate, NoteUpdate
```
For `AuthRepository`, replace the notes imports with `from app.auth.models import User, RefreshToken` and `from app.auth.schemas import UserCreate`.

---

### `app/auth/service.py` (service, request-response)

**Analog:** `app/notes/service.py`

**Class + constructor pattern** (`app/notes/service.py` lines 19-22):
```python
class NoteService:
    """Service layer for Note CRUD operations."""

    def __init__(self, repo: NoteRepository) -> None:
        self._repo = repo
```
`AuthService.__init__` is identical: `self._repo = repo` (typed `AuthRepository`). May also accept `settings` for JWT secret access.

**HTTPException raise pattern** (`app/notes/service.py` lines 29-36):
```python
async def get_or_404(self, note_id: int) -> Note:
    """Return the note with the given id, or raise HTTP 404."""
    note = await self._repo.get_by_id(note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return note
```
Auth service raises HTTP 409 (duplicate email), HTTP 401 (invalid credentials/token), HTTP 401 (revoked jti) using the same `raise HTTPException(status_code=..., detail=...)` pattern.

**ValueError → HTTPException translation pattern** (`app/notes/service.py` lines 61-69):
```python
try:
    items, total = await self._repo.list_paginated(page, size, sort, filter)
except ValueError as exc:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    ) from exc
```
Auth service catches `IntegrityError` (duplicate email) and translates it to HTTP 409 using the same try/except translation pattern.

**Imports pattern** (`app/notes/service.py` lines 11-16):
```python
from fastapi import HTTPException, status

from app.notes.models import Note
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteListResponse, NoteUpdate
```
For `AuthService`, replace notes imports with auth equivalents; add `import jwt`, `import uuid`, `from datetime import datetime, timezone, timedelta`, `from pwdlib import PasswordHash`.

---

### `app/auth/router.py` (controller, request-response)

**Analog:** `app/notes/router.py`

**Router factory + service construction pattern** (`app/notes/router.py` lines 35-40):
```python
router = APIRouter(tags=["notes"])


def _make_service(session: AsyncSession) -> NoteService:
    """Construct NoteService with its repository for the current request session."""
    return NoteService(NoteRepository(session))
```
`app/auth/router.py` uses the same pattern: `router = APIRouter(tags=["auth"])` and a `_make_service(session)` helper that returns `AuthService(AuthRepository(session))`.

**POST endpoint returning 201 pattern** (`app/notes/router.py` lines 64-76):
```python
@router.post(
    "/",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
async def create_note(
    data: NoteCreate,
    session: AsyncSession = Depends(get_db),
) -> NoteRead:
    """POST /notes/ — create a new note and return it."""
    note = await _make_service(session).create(data)
    return NoteRead.model_validate(note)
```
`POST /auth/register` → 201 follows the same shape with `UserCreate` body and `UserRead` response.

**POST endpoint returning 200 (login, refresh)** — copy from `GET` handler pattern (`app/notes/router.py` lines 79-91), changing to `status_code=status.HTTP_200_OK` (default) and the appropriate schemas.

**DELETE-like endpoint returning 204 (logout)** (`app/notes/router.py` lines 110-121):
```python
@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
)
async def delete_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /notes/{note_id} — delete a note or return 404."""
    await _make_service(session).delete(note_id)
```
`POST /auth/logout` → 204 uses this same `status_code=HTTP_204_NO_CONTENT` + `-> None` return type pattern.

**Imports pattern** (`app/notes/router.py` lines 27-33):
```python
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteCreate, NoteListResponse, NoteRead, NoteUpdate
from app.notes.service import NoteService
```
For `app/auth/router.py`, replace notes imports with auth equivalents; remove `Query` (no query params on auth endpoints).

---

### `app/core/dependencies.py` (middleware, request-response) — MODIFY EXISTING

**Analog:** `app/core/dependencies.py` (the file itself)

**Existing `get_db` pattern** (`app/core/dependencies.py` lines 26-29) — unchanged, keep as-is:
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; close it cleanly on response completion."""
    async with AsyncSessionLocal() as session:
        yield session
```

**Existing service factory pattern** (`app/core/dependencies.py` lines 32-36):
```python
async def get_note_service(
    db: AsyncSession = Depends(get_db),
) -> NoteService:
    """Construct NoteService with its repository for the current request."""
    return NoteService(NoteRepository(db))
```
`get_current_user` follows the same `Depends(get_db)` injection pattern, but also receives `HTTPAuthorizationCredentials` from `HTTPBearer`, does `jwt.decode(...)`, fetches the user by id via a lightweight repository call, and raises `HTTPException(401)` on any failure. See RESEARCH.md Pattern 2 for the full implementation.

**New imports to add at the top of the file:**
```python
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from app.auth.models import User
from app.auth.repository import AuthRepository
from app.core.config import settings
```

---

### `app/core/config.py` (config) — MODIFY EXISTING

**Analog:** `app/core/config.py` (the file itself)

**Existing settings pattern** (`app/core/config.py` lines 1-24) — the whole file is the pattern. Add four new fields inside the `Settings` class, preserving `extra="ignore"` and `SettingsConfigDict`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "mysql+asyncmy://..."

    # JWT (Phase 3) — add these four fields:
    jwt_secret_key: str = "changeme-jwt-secret-key-minimum-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


settings = Settings()
```

---

### `app/main.py` (config) — MODIFY EXISTING

**Analog:** `app/main.py` (the file itself)

**Router registration pattern** (`app/main.py` lines 53-54):
```python
app.include_router(health_router)
app.include_router(notes_router, prefix="/notes")
```
Add one more line in the same style:
```python
from app.auth.router import router as auth_router
# ...
app.include_router(auth_router, prefix="/auth")
```
The import at the top of the file follows the same `from app.X.router import router as X_router` pattern (`app/main.py` lines 23-25).

---

### `app/notes/models.py` (model, CRUD) — MODIFY EXISTING

**Analog:** `app/notes/models.py` (the file itself)

**New FK column to add** — mirrors the `INTEGER(unsigned=True)` PK pattern already in the file (line 35-37), and adds `ForeignKey`:

```python
# Add after existing column declarations, before created_at:
user_id: Mapped[int] = mapped_column(
    INTEGER(unsigned=True),
    ForeignKey("users.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
    comment="Owner user — added Phase 3",
)
```

**New relationship to add** (back-ref to User):
```python
owner: Mapped["User"] = relationship(back_populates="notes")
```

**New imports needed:**
```python
from sqlalchemy import ForeignKey  # add to existing sqlalchemy import
from sqlalchemy.orm import relationship  # add to existing orm import
```

---

### `app/notes/repository.py` (service, CRUD) — MODIFY EXISTING

**Analog:** `app/notes/repository.py` (the file itself)

**`create` method change** — add `user_id: int` parameter (D-10). Copy the existing `create` pattern (`app/notes/repository.py` lines 33-43) and add `user_id=user_id` to the `Note(...)` constructor call:
```python
async def create(self, data: NoteCreate, user_id: int) -> Note:
    note = Note(
        title=data.title,
        content=data.content,
        source_url=data.source_url,
        user_id=user_id,            # new — set server-side
    )
    self._session.add(note)
    await self._session.commit()
    await self._session.refresh(note)
    return note
```

**`list_paginated` method change** — add `user_id: int` parameter. Copy the existing WHERE clause pattern (`app/notes/repository.py` lines 88-90) and add a `user_id` filter after the base query is built:
```python
query = select(Note)
query = query.where(Note.user_id == user_id)    # new — scope to owner
if filter:
    query = query.where(Note.content.ilike(f"%{filter}%"))
```

**`get_by_id` method** (`app/notes/repository.py` lines 45-48) — stays unchanged. The ownership check (403 vs 404) is the service's responsibility, not the repository's.

---

### `app/notes/service.py` (service, request-response) — MODIFY EXISTING

**Analog:** `app/notes/service.py` (the file itself)

**`create` method change** — add `user_id: int` parameter and pass it down. Copy existing `create` (`app/notes/service.py` lines 25-27):
```python
async def create(self, data: NoteCreate, user_id: int) -> Note:
    """Create and persist a new note owned by user_id."""
    return await self._repo.create(data, user_id)
```

**New `get_or_404_owned` method** — extends the existing `get_or_404` pattern (`app/notes/service.py` lines 29-37) with the ownership check (D-08):
```python
async def get_or_404_owned(self, note_id: int, current_user: "User") -> Note:
    """Return the note or raise 404 (missing) / 403 (wrong owner)."""
    note = await self._repo.get_by_id(note_id)
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    if note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden",
        )
    return note
```

**`list_notes` method change** — add `user_id: int` parameter, pass to `_repo.list_paginated`. Copy the existing signature (`app/notes/service.py` lines 39-45) and add the parameter; the try/except error-translation block (`lines 61-69`) is unchanged.

**`update` and `delete` method changes** — replace `get_or_404` calls with `get_or_404_owned(note_id, current_user)`. Add `current_user` parameter to both methods.

---

### `app/notes/router.py` (controller, request-response) — MODIFY EXISTING

**Analog:** `app/notes/router.py` (the file itself)

**Adding `get_current_user` dependency** — each handler gains one extra parameter. Copy the existing `Depends(get_db)` pattern (all handler signatures, e.g. lines 53-58) and add:
```python
from app.core.dependencies import get_current_user
from app.auth.models import User

# In every handler:
current_user: User = Depends(get_current_user),
```

**Handler change for `create_note`** — pass `current_user.id` to service:
```python
async def create_note(
    data: NoteCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    note = await _make_service(session).create(data, user_id=current_user.id)
    return NoteRead.model_validate(note)
```

**Handler change for single-note endpoints** — replace `get_or_404` with `get_or_404_owned(note_id, current_user)`:
```python
async def get_note(
    note_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    note = await _make_service(session).get_or_404_owned(note_id, current_user)
    return NoteRead.model_validate(note)
```

**Handler change for `list_notes`** — add `current_user` and pass `user_id=current_user.id` to service:
```python
async def list_notes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at"),
    filter: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteListResponse:
    return await _make_service(session).list_notes(
        page=page, size=size, sort=sort, filter=filter, user_id=current_user.id
    )
```

---

### `app/notes/schemas.py` (model, request-response) — MODIFY EXISTING

**Analog:** `app/notes/schemas.py` (the file itself)

`NoteCreate` — remove `user_id` if it was ever added; keep the existing three fields unchanged (D-10: `user_id` is never accepted from client body).

`NoteRead` — add `user_id: int` field to the response schema (lines 62-75). This lets API consumers know the owner without exposing the full User object.

No other changes required.

---

### `alembic/env.py` (config) — MODIFY EXISTING

**Analog:** `alembic/env.py` (the file itself)

**Model import block** (`alembic/env.py` lines 40-42) — add the two new auth models:
```python
from app.database import Base  # noqa: E402
from app.notes.models import Note  # noqa: E402, F401
# Add these two lines (Pitfall 6 — must import before target_metadata):
from app.auth.models import User  # noqa: E402, F401
from app.auth.models import RefreshToken  # noqa: E402, F401

target_metadata = Base.metadata
```
All other env.py content (`run_migrations_offline`, `do_run_migrations`, `run_async_migrations`, `run_migrations_online`, the offline/online dispatch at the bottom) stays identical.

---

### `alembic/versions/XXXX_create_users_and_refresh_tokens.py` (migration, CRUD)

**Analog:** `alembic/versions/d51191e92276_create_notes_table.py`

**File header pattern** (`d51191e92276_create_notes_table.py` lines 1-21):
```python
"""create users and refresh_tokens tables

Revision ID: XXXX
Revises: d51191e92276
Create Date: ...
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "XXXX"
down_revision: str | Sequence[str] | None = "d51191e92276"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```
Note `down_revision = "d51191e92276"` (the existing notes migration is the parent).

**`op.create_table` pattern** (`d51191e92276_create_notes_table.py` lines 40-68):
```python
op.create_table(
    "notes",
    sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
    sa.Column("title", sa.String(512), nullable=True, comment="Optional note title"),
    sa.Column("content", sa.Text(length=4294967295), nullable=False, comment="..."),
    sa.Column("created_at", sa.DateTime(), nullable=False,
              server_default=sa.text("CURRENT_TIMESTAMP")),
    sa.Column("updated_at", sa.DateTime(), nullable=False,
              server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
    mysql_collate="utf8mb4_unicode_ci",
)
```
`users` table: same pattern with `email` (String(255) unique), `hashed_password` (String(255)), `created_at`. Add `op.create_index("ix_users_email", "users", ["email"], unique=True)` after table creation.
`refresh_tokens` table: same pattern with `jti` (String(36) unique), `user_id` (INTEGER unsigned FK), `expires_at` (DateTime), `revoked` (Boolean), `revoked_at` (DateTime nullable), `created_at`.

**`downgrade` pattern** (`d51191e92276_create_notes_table.py` lines 77-79):
```python
def downgrade() -> None:
    op.drop_table("notes")
```
For the users migration, `downgrade` must drop in reverse FK order: `op.drop_table("refresh_tokens")` then `op.drop_table("users")`.

---

### `alembic/versions/YYYY_add_user_id_to_notes.py` (migration, CRUD)

**Analog:** `alembic/versions/d51191e92276_create_notes_table.py` (role-match)

**File header** — same structure as above; `down_revision = "XXXX"` (pointing to the users migration).

**`op.execute` for raw DDL pattern** (`d51191e92276_create_notes_table.py` lines 71-73):
```python
op.execute(
    "ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)"
)
```
Use `op.execute("TRUNCATE TABLE notes")` (D-11) in the same style before adding the FK column.

**`op.add_column` pattern** — from RESEARCH.md Pattern 6; no direct Phase 2 analog. The migration sequence is: TRUNCATE → add_column nullable → create_foreign_key → alter_column NOT NULL → create_index. Follow RESEARCH.md Pattern 6 exactly.

**`downgrade` pattern** for this migration: reverse of upgrade — `op.drop_index`, `op.drop_constraint`, `op.drop_column`.

---

### `tests/conftest.py` (test) — MODIFY EXISTING

**Analog:** `tests/conftest.py` (the file itself)

**Session-scoped fixtures to keep unchanged** (`tests/conftest.py` lines 36-72): `mysql_container`, `test_database_url`, `run_migrations`, `test_engine` — all kept verbatim. The same MySQL container and Alembic head run will now include the new tables.

**Per-test `session` fixture — keep unchanged** (`tests/conftest.py` lines 78-91):
```python
@pytest_asyncio.fixture
async def session(test_engine) -> AsyncSession:
    async with test_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with session_factory() as sess:
            yield sess
        await conn.rollback()
```

**`client` fixture — keep unchanged** (`tests/conftest.py` lines 94-110):
```python
@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```

**New fixtures to add** — function-scoped, reuse the existing `client` fixture:
```python
@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Create a test user via POST /auth/register."""
    resp = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Test1234!",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, registered_user: dict) -> AsyncClient:
    """AsyncClient pre-authenticated with the registered user's access token."""
    resp = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "Test1234!",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```
For cross-user isolation tests, add `user_a_client` and `user_b_client` fixtures that register two distinct users (different emails) and return separately-authenticated clients.

---

### `tests/test_auth.py` (test, request-response) — NEW FILE

**Analog:** `tests/test_notes_crud.py`

**File-level docstring pattern** (`tests/test_notes_crud.py` lines 1-22) — copy structure, describe coverage in plain English at top.

**Test function signature pattern** (`tests/test_notes_crud.py` lines 27-30):
```python
async def test_create_note_returns_201(client: httpx.AsyncClient) -> None:
    """POST /notes/ with valid body should return 201 and the created note."""
    response = await client.post("/notes/", json={"content": "hello"})
    assert response.status_code == 201
```
All auth tests use the same `async def test_X(client: httpx.AsyncClient) -> None` signature. Use `client` fixture (unauthenticated) for register and login tests; `auth_client` fixture for protected-endpoint tests.

**404/401 assert pattern** (`tests/test_notes_crud.py` lines 67-71):
```python
async def test_get_nonexistent_note_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/notes/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"
```
Error-detail assertions follow the same `assert response.json()["detail"] == "..."` pattern.

**Multi-step test pattern** (`tests/test_notes_crud.py` lines 88-98) — create → act → assert:
```python
async def test_delete_note_returns_204_then_404(client: httpx.AsyncClient) -> None:
    create_resp = await client.post("/notes/", json={"content": "To be deleted"})
    note_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/notes/{note_id}")
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    get_resp = await client.get(f"/notes/{note_id}")
    assert get_resp.status_code == 404
```
The refresh/rotation test (`test_refresh_rotation`) and logout test (`test_logout_revokes_token`) use the same multi-step pattern: login → act → assert downstream.

---

### `tests/test_notes_isolation.py` (test, request-response) — NEW FILE

**Analog:** `tests/test_notes_crud.py` (role-match)

**Multi-user test structure** — extends the multi-step pattern with two clients. Use `user_a_client` and `user_b_client` fixtures (defined in `conftest.py`):
```python
async def test_cross_user_note_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User A cannot read User B's note — 403 (D-08)."""
    # Step 1: User A creates a note
    note_resp = await user_a_client.post("/notes/", json={"content": "A's secret"})
    assert note_resp.status_code == 201
    note_id = note_resp.json()["id"]

    # Step 2: User B tries to read it
    resp = await user_b_client.get(f"/notes/{note_id}")
    assert resp.status_code == 403
```

**List isolation test** — follows the same multi-step pattern: seed notes from two users → assert each user's GET /notes/ only returns their own:
```python
async def test_list_notes_isolates_per_user(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    await user_a_client.post("/notes/", json={"content": "A only"})
    await user_b_client.post("/notes/", json={"content": "B only"})

    resp = await user_a_client.get("/notes/")
    items = resp.json()["items"]
    assert all("B only" != item["content"] for item in items)
    assert any("A only" == item["content"] for item in items)
```

---

### `tests/test_notes_crud.py` and `tests/test_notes_list.py` (test) — MODIFY EXISTING

**Analog:** Both files themselves.

The only change is to replace the `client` fixture argument with `auth_client` in every test function signature. The test bodies are unchanged:

```python
# Before (Phase 2):
async def test_create_note_returns_201(client: httpx.AsyncClient) -> None:

# After (Phase 3):
async def test_create_note_returns_201(auth_client: httpx.AsyncClient) -> None:
    # Body identical — auth_client has Bearer token pre-set
```

Both files import `httpx` only (lines 1 in each). No other imports change.

---

## Shared Patterns

### `get_db` dependency injection
**Source:** `app/core/dependencies.py` lines 26-29 and `tests/conftest.py` lines 101-110
**Apply to:** Every router handler, all existing and new service factories, test `client` fixture
```python
# In handlers:
session: AsyncSession = Depends(get_db)

# In tests (dependency override):
app.dependency_overrides[get_db] = override_get_db
# ... always followed by:
app.dependency_overrides.clear()   # in finally/teardown
```

### Constructor injection (session → repository → service)
**Source:** `app/core/dependencies.py` lines 32-36 and `app/notes/router.py` lines 38-40
**Apply to:** `app/auth/router.py` (`_make_service` helper), `app/core/dependencies.py` (`get_current_user` internal repo call)
```python
def _make_service(session: AsyncSession) -> NoteService:
    return NoteService(NoteRepository(session))
```

### `__table_args__` InnoDB/utf8mb4 block
**Source:** `app/notes/models.py` lines 28-33
**Apply to:** `app/auth/models.py` `User` class, `app/auth/models.py` `RefreshToken` class
```python
__table_args__ = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}
```

### Migration `op.create_table` with `mysql_engine/charset/collate` kwargs
**Source:** `alembic/versions/d51191e92276_create_notes_table.py` lines 40-68
**Apply to:** Both new migration files (`create_users_and_refresh_tokens`, `add_user_id_to_notes` does not use create_table but uses the same `mysql.*` dialect import)

### HTTPException with `status` enum constants
**Source:** `app/notes/service.py` lines 29-37
**Apply to:** `app/auth/service.py` (401, 409), `app/notes/service.py` (403 new addition), `app/core/dependencies.py` (401)
```python
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Note not found",
)
```

### Transaction-rollback test isolation
**Source:** `tests/conftest.py` lines 78-110
**Apply to:** All new test files. All tests reuse the existing `session` and `client` fixtures without modification — the rollback pattern applies automatically.

### `model_validate(orm_obj)` serialization
**Source:** `app/notes/router.py` lines 76, 91, 107
**Apply to:** `app/auth/router.py` for `POST /auth/register` response (`UserRead.model_validate(user)`)
```python
return NoteRead.model_validate(note)
```

---

## No Analog Found

All files have close Phase 2 analogs. The following aspects have no direct codebase analog and should use RESEARCH.md patterns instead:

| Aspect | Role | Data Flow | Reason |
|--------|------|-----------|--------|
| `create_access_token` / `create_refresh_token` functions inside `app/auth/service.py` | utility | — | No JWT issuance exists yet — use RESEARCH.md Pattern 1 |
| `get_current_user` dependency body in `app/core/dependencies.py` | middleware | request-response | No bearer token validation exists yet — use RESEARCH.md Pattern 2 |
| `rotate_refresh_token` logic in `app/auth/service.py` | service | request-response | No token rotation exists yet — use RESEARCH.md Pattern 3 |
| `pwdlib.PasswordHash` usage in `app/auth/service.py` | utility | — | No password hashing exists yet — use RESEARCH.md Pattern 7 |
| `@field_validator` for password complexity in `app/auth/schemas.py` | model | — | No field validators exist yet — use RESEARCH.md Code Examples section |

---

## Metadata

**Analog search scope:** `app/`, `tests/`, `alembic/`
**Files scanned:** 23 Python files (full codebase)
**Pattern extraction date:** 2026-06-25
