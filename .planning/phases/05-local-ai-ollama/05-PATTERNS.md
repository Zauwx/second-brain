# Phase 5: Local AI (Ollama) - Pattern Map

**Mapped:** 2026-07-05
**Files analyzed:** 16 (new) + 6 (modified)
**Analogs found:** 20 / 22 (2 no-analog: `providers/protocol.py`, `providers/ollama.py` — new abstraction, RESEARCH.md Code Examples are the primary reference)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `app/ai/__init__.py` | package init | — | `app/tags/__init__.py` | exact |
| `app/ai/router.py` | router | request-response | `app/tags/router.py` (note-scoped POST, 401/403/404 responses table) | exact |
| `app/ai/schemas.py` | model (Pydantic schema) | request-response | `app/tags/schemas.py` (small request/response pair, no list-envelope) | exact |
| `app/ai/service.py` | service | request-response, transform | `app/tags/service.py` (composes `NoteRepository` + reuses ownership check) and `app/search/service.py` (sanitize/parse untrusted input before persisting/returning) | role-match (composite of two) |
| `app/ai/prompts.py` | utility | transform | *(no analog — new concern)* | none |
| `app/ai/providers/__init__.py` | package init | — | `app/tags/__init__.py` | exact |
| `app/ai/providers/protocol.py` | utility (interface) | transform | *(no analog — first Protocol in codebase)* | none — use RESEARCH.md Pattern 1 verbatim |
| `app/ai/providers/ollama.py` | service (external client wrapper) | request-response (outbound HTTP) | *(no analog — first outbound-HTTP-to-sibling-container client)* | none — use RESEARCH.md Pattern 2 verbatim |
| `app/notes/models.py` (modified) | model | CRUD | itself (existing `Note` class, same file) | exact |
| `app/notes/schemas.py` (modified) | model (Pydantic schema) | CRUD | itself (existing `NoteRead`, same file) | exact |
| `app/notes/repository.py` (modified — add `set_summary`) | model/repository | CRUD | itself; shape mirrors existing `update()` method (same file) | exact |
| `app/core/config.py` (modified) | config | — | itself (existing `Settings` class, same file) | exact |
| `app/core/dependencies.py` (modified) | middleware (DI provider) | — | itself — `get_search_service`/`get_collection_service` (two-repo composition) as the template for `get_ai_service`; `get_db` as the override seam pattern | exact |
| `app/main.py` (modified) | route (app assembly) | — | itself — existing `include_router` block, same file | exact |
| `app/api/health.py` (modified) | route (health probe) | request-response | itself (existing `health_check`, same file) | exact |
| `docker-compose.yml` (modified) | config | — | itself — existing `mysql` service block (healthcheck + `depends_on` + internal network pattern), same file | role-match |
| `alembic/versions/0006_add_note_summary.py` | migration | CRUD (schema) | `alembic/versions/0003_add_user_id_to_notes.py` (single nullable-column `add_column` on `notes`, no new table) | exact |
| `tests/conftest.py` (modified — add `FakeLLMProvider` + `ai_client` fixture) | test fixture | request-response (mocked) | itself — existing `client`/`get_db` override pattern (same file) | exact |
| `tests/test_ai.py` | test | request-response | `tests/test_tags.py` (note-scoped POST endpoint tests with ownership 403/404 cases) | exact |
| `tests/test_health.py` (modified — add Ollama-reachability case) | test | request-response | itself (existing `test_health_returns_200_and_ok_body`, same file) | exact |

## Pattern Assignments

### `app/ai/router.py` (router, request-response)

**Analog:** `app/tags/router.py`

**Imports pattern** (`app/tags/router.py` lines 15-24):
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.notes.repository import NoteRepository
from app.notes.schemas import NoteRead
from app.tags.repository import TagRepository
from app.tags.schemas import TagCreate, TagRead
from app.tags.service import TagService

router = APIRouter(tags=["tags"])
```
For `app/ai/router.py`, mirror this exactly but import `get_ai_service` from `app.core.dependencies` (preferred — see Dependency section below) instead of hand-building the service in a router-local `_make_service` helper, since `AIService` needs a `provider` dependency too (three inputs: db, provider, note repo) — cleaner to construct it in `app/core/dependencies.py::get_ai_service` and `Depends()` it directly.

**Auth + note-scoped POST pattern** (`app/tags/router.py` lines 71-79):
```python
@router.post(
    "/notes/{note_id}/tags",
    response_model=NoteRead,
    status_code=status.HTTP_200_OK,
    summary="Attach a tag to a note",
    responses={
        401: {"description": "Missing or invalid access token"},
        403: {"description": "Note is owned by another user"},
        404: {"description": "Note not found"},
    },
)
async def attach_tag(
    note_id: int,
    data: TagCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteRead:
    """POST /notes/{note_id}/tags — attach a tag to a note (T-04-iso)."""
    note = await _make_service(session).attach_tag(note_id, data.name, current_user)
    return NoteRead.model_validate(note)
```
Copy this shape for both `POST /ai/summarize` and `POST /ai/suggest-tags`: request body carries `note_id` (per D-Discretion-3, RESEARCH.md recommends `{"note_id": int}` body rather than a path param since both endpoints operate on an arbitrary note, not a fixed resource root), `Depends(get_current_user)` for 401, and a `responses={401, 403, 404, 503}` table — add `503: {"description": "Local AI service unavailable"}` to the table (new status code this phase, no existing analog for it in a router `responses=` dict — add it fresh).

**No-`_make_service`-helper alternative:** Because `AIService` needs 3 collaborators (provider, note_service, note_repo), prefer wiring it entirely through `app/core/dependencies.py::get_ai_service` (see Dependency Wiring below) rather than a router-local `_make_service(session)` closure like tags/notes use — this also gives tests the single override seam (`get_llm_provider`) specified by D-10 without needing to reach through router internals.

---

### `app/ai/schemas.py` (schemas, request-response)

**Analog:** `app/tags/schemas.py`

**Pattern** (`app/tags/schemas.py` lines 11-27, full file):
```python
from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    """Request body for tagging a note — just the name."""

    name: str = Field(min_length=1, max_length=128)


class TagRead(BaseModel):
    """Response schema for a single tag."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int
```
For `app/ai/schemas.py`, define (no ORM-backed schema needed since AI responses are plain values, not model-validated ORM rows):
```python
class SummarizeRequest(BaseModel):
    note_id: int

class SummarizeResponse(BaseModel):
    note_id: int
    summary: str

class SuggestTagsRequest(BaseModel):
    note_id: int

class SuggestTagsResponse(BaseModel):
    tags: list[str]
```
Note: `SummarizeResponse` could instead just be `NoteRead` (already gains a `summary` field per D-02) — planner's call; either satisfies criterion 2. If reusing `NoteRead`, import it from `app.notes.schemas` exactly as `app/tags/router.py` does (line 21) rather than redefining fields.

---

### `app/ai/service.py` (service, request-response + transform)

**Analog:** `app/tags/service.py` (ownership/composition shape) + `app/search/service.py` (sanitize-before-use shape)

**Ownership composition pattern** (`app/tags/service.py` lines 26-50):
```python
class TagService:
    """Service layer for Tag CRUD + note-attachment operations."""

    def __init__(self, repo: TagRepository, note_repo: NoteRepository) -> None:
        self._repo = repo
        self._note_repo = note_repo

    async def get_or_404_owned(self, note_id: int, current_user: User) -> Note:
        """Return the note or raise 404 (missing) / 403 (wrong owner) (T-04-iso).

        Mirrors NoteService.get_or_404_owned — copy of the ownership pattern
        so TagService can protect all tag-mutation endpoints.
        """
        note = await self._note_repo.get_by_id(note_id)
        if note is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
        if note.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")
        return note
```
**IMPORTANT — do not re-implement this check a third time.** RESEARCH.md's `AIService` example (already correct) composes the *existing* `NoteService` and calls `NoteService.get_or_404_owned` directly rather than duplicating the note/403/404 logic a third time the way `TagService` does. Prefer that: `AIService.__init__(self, provider, note_service: NoteService, note_repo: NoteRepository)` — inject the real `NoteService` (constructed the same way `get_note_service` does in `app/core/dependencies.py`), not a hand-rolled copy. This is more DRY than the Tag precedent and should be the version the planner ships.

**Sanitize/validate untrusted external input before use** (`app/search/service.py` lines 59-83, the `SearchService.search` shape — LLM output here plays the same "untrusted string that needs defensive parsing before being treated as structured data" role that the raw search query plays there):
```python
class SearchService:
    def __init__(self, repo: SearchRepository) -> None:
        self._repo = repo

    async def search(self, q: str, page: int, size: int, user_id: int) -> NoteListResponse:
        clean_q = sanitize_boolean_query(q)
        if clean_q is None:
            return NoteListResponse(items=[], total=0, page=page, size=size, pages=0)
        items, total = await self._repo.search_fulltext(clean_q, user_id, page, size)
        ...
```
Mirror this "sanitize function lives at module level, service calls it and degrades gracefully to an empty/default result rather than raising" shape for `_parse_tag_list` (RESEARCH.md Pattern 4) — same rationale: never let malformed external input surface as a 500.

**Full recommended `AIService`** — use RESEARCH.md's Code Examples verbatim (Pattern 3, lines 291-328 of 05-RESEARCH.md): constructor takes `(provider: LLMProvider, note_service: NoteService, note_repo: NoteRepository)`; `summarize()` and `suggest_tags()` both call `self._notes.get_or_404_owned(note_id, current_user)` first (reuses the real `NoteService`, per the "do not duplicate" note above); `_safe_complete()` is the single place that catches `(ConnectionError, TimeoutError, OSError)` and raises `HTTPException(503, ...)` — this mirrors the project's established rule (seen in `NoteService`/`SearchService`) that **only the service layer raises `HTTPException`**, never the repository or provider.

**Error-handling pattern reference** (`app/notes/service.py` lines 100-107 — the existing precedent for "repository/domain exception → HTTPException translated in the service layer, never a bare 500"):
```python
try:
    items, total = await self._repo.list_paginated(...)
except ValueError as exc:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    ) from exc
```
Apply the same shape for AI: `try: await provider.complete(...) except (ConnectionError, httpx.TimeoutException, ollama.ResponseError) as exc: raise HTTPException(503, ...) from exc`. Per RESEARCH.md Common Pitfall 1, also catch `ollama.ResponseError` (raised for "model not found") alongside connection/timeout errors — not just the two exception types shown in the RESEARCH.md snippet — so a not-yet-pulled model degrades to 503, not 500.

---

### `app/ai/providers/protocol.py` and `app/ai/providers/ollama.py` (no in-repo analog)

No existing file in this codebase defines a `Protocol` or wraps an outbound HTTP client to a sibling Docker service — this is genuinely new infrastructure for Phase 5. Use RESEARCH.md's Pattern 1 (Protocol) and Pattern 2 (tenacity-wrapped `OllamaProvider`) verbatim as the primary source — both are already fully worked out with citations to the official `ollama-python` GitHub source. Follow the project's general conventions seen elsewhere (module docstring explaining intent + decision IDs, `from __future__ import annotations` where the file uses forward-referenced types as `app/notes/service.py` and `app/tags/service.py` do).

---

### `app/notes/models.py` (model, CRUD) — add `summary` column

**Analog:** itself — existing `Note` class (same file, lines 84-142)

**Pattern to copy** — the existing nullable-column style already used for `title`/`source_url` (lines 97-107):
```python
title: Mapped[str | None] = mapped_column(
    String(512), nullable=True, comment="Optional note title"
)
...
source_url: Mapped[str | None] = mapped_column(
    String(2048), nullable=True, comment="URL of the original source"
)
```
Add directly below `source_url` (or near `content`, planner's call):
```python
summary: Mapped[str | None] = mapped_column(
    Text(length=65535),  # TEXT — generous for a 2-3 sentence LLM summary
    nullable=True,
    comment="AI-generated summary (Phase 5, D-02) — null until /ai/summarize is called",
)
```
`Text` is already imported in this file (line 26). Update the module docstring's "Column notes" section (lines 13-18) with a `summary` bullet, matching the existing documentation convention.

---

### `app/notes/schemas.py` (schema, CRUD) — surface `summary` in `NoteRead`

**Analog:** itself — existing `NoteRead` (same file, lines 78-95)

**Pattern to copy** (lines 85-94):
```python
class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    content: str
    source_url: str | None
    user_id: int
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead] = []
```
Add `summary: str | None` alongside the other nullable fields (e.g. after `source_url` or near the end) — `from_attributes=True` means no other change is needed; the ORM attribute added to `Note` maps automatically.

---

### `app/notes/repository.py` (repository, CRUD) — add `set_summary`

**Analog:** itself — existing `update()` method (same file, lines 165-182)

**Pattern to copy** (lines 165-182):
```python
async def update(self, note: Note, data: NoteUpdate) -> Note:
    """Apply the explicitly-set fields from NoteUpdate to the Note instance."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(note, field, value)
    await self._session.commit()
    # Re-fetch via get_by_id so selectinload(Note.tags) is applied.
    updated = await self.get_by_id(note.id)
    assert updated is not None  # we just committed it
    return updated
```
RESEARCH.md already provides the exact `set_summary` method to add (Code Examples § `NoteRepository.set_summary`, lines 489-501 of 05-RESEARCH.md) — it follows this identical commit → re-fetch-via-`get_by_id` → assert-not-None shape, explicitly called out in its own docstring as intentionally separate from `update()` because `NoteUpdate`'s client-facing validation rules don't apply to this server-side-only write. Use it as written.

---

### `app/core/config.py` (config) — add Ollama settings

**Analog:** itself — existing `Settings` class (same file, lines 9-57)

**Pattern to copy** (lines 17-33, showing the existing grouped-by-comment-header convention):
```python
model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Application
environment: str = "development"
log_level: str = "INFO"

# Database — MySQL via asyncmy + SQLAlchemy 2
database_url: str = "mysql+asyncmy://secondbrain:changeme-password@mysql:3306/secondbrain?charset=utf8mb4"

# JWT (Phase 3) — read from .env; defaults are safe-looking-but-insecure placeholders.
jwt_secret_key: str = "changeme-jwt-secret-key-minimum-32-bytes-long"
jwt_algorithm: str = "HS256"
access_token_expire_minutes: int = 15
refresh_token_expire_days: int = 7
```
Add a new `# Ollama (Phase 5)` group in the same style (RESEARCH.md Code Examples already has the exact block, lines 444-452 of 05-RESEARCH.md):
```python
# Ollama (Phase 5) — .env.example already documents these keys
ollama_base_url: str = "http://ollama:11434"
ollama_chat_model: str = "llama3.2:3b"
ollama_timeout_seconds: float = 30.0
ollama_max_retries: int = 3
```
`extra="ignore"` (line 17, already present, docstring at lines 12-15 explicitly calls out "future phases: JWT, Anthropic, **Ollama**") — no restructuring needed, this is exactly what that config was built to tolerate. No `@model_validator` guard is needed for Ollama settings (unlike `jwt_secret_key`'s `_require_secret_outside_dev`, lines 35-54) since Ollama has no secret/auth token in this internal-network-only setup.

---

### `app/core/dependencies.py` (DI providers) — add `get_llm_provider` / `get_ai_service`

**Analog:** itself — `get_search_service` / `get_collection_service` (multi-repo composition pattern, same file, lines 70-81) and `get_db` (the override-seam pattern, lines 50-53)

**Two-collaborator service-provider pattern** (lines 70-81):
```python
async def get_collection_service(
    db: AsyncSession = Depends(get_db),
) -> CollectionService:
    """Construct CollectionService with its repositories for the current request."""
    return CollectionService(CollectionRepository(db), NoteRepository(db))


async def get_search_service(
    db: AsyncSession = Depends(get_db),
) -> SearchService:
    """Construct SearchService with its repository for the current request."""
    return SearchService(SearchRepository(db))
```
**Override-seam pattern** (`get_db`, lines 50-53 — the mechanism tests already rely on):
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; close it cleanly on response completion."""
    async with AsyncSessionLocal() as session:
        yield session
```
Add, mirroring both shapes plus RESEARCH.md's already-correct example (Code Examples § "Dependency wiring", lines 456-483 of 05-RESEARCH.md — use as-is):
```python
def get_llm_provider() -> LLMProvider:
    """Construct the OllamaProvider from settings.

    This is the seam tests override via app.dependency_overrides (D-10) —
    zero real Ollama calls happen in pytest because this function is never
    invoked; a fake LLMProvider is substituted instead.
    """
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_chat_model,
        timeout=settings.ollama_timeout_seconds,
    )


async def get_ai_service(
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
) -> AIService:
    note_repo = NoteRepository(db)
    return AIService(provider, NoteService(note_repo), note_repo)
```
Add the corresponding imports at the top of the file next to the existing `app.notes.service`/`app.tags.service` imports (lines 34-39): `from app.ai.providers.ollama import OllamaProvider`, `from app.ai.providers.protocol import LLMProvider`, `from app.ai.service import AIService`.

---

### `app/main.py` (app assembly) — register the `ai` router

**Analog:** itself — existing router-registration block (same file, lines 23-29, 57-62)

**Pattern to copy** (lines 57-62):
```python
app.include_router(health_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(notes_router, prefix="/notes")
app.include_router(tags_router)  # no prefix — owns /tags and /notes/{id}/tags
app.include_router(collections_router, prefix="/collections")
app.include_router(search_router, prefix="/search")
```
Add:
```python
from app.ai.router import router as ai_router
...
app.include_router(ai_router, prefix="/ai")
```
Note the existing docstring at lines 38-39 already anticipates this: *"Future phases will add Qdrant and Ollama client initialisation in startup."* — no lifespan changes are required for Phase 5 since `OllamaProvider` is constructed per-request via DI (`get_llm_provider`), not at app startup; leave `lifespan()` (lines 32-44) untouched.

---

### `app/api/health.py` (health probe) — extend for Ollama reachability

**Analog:** itself — existing `health_check` (same file, full content, 9 lines)

**Current pattern** (lines 1-9):
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint — smoke test for 'the service is reachable'."""
    return {"status": "ok"}
```
Extend to probe Ollama with a short timeout, staying "degraded-but-200" per D-07 philosophy (do not fail the whole health check because an optional dependency is down — this matches RESEARCH.md's diagram note, lines 179-181 of 05-RESEARCH.md):
```python
@router.get("/health")
async def health_check() -> dict[str, str]:
    ollama_status = "ok"
    try:
        client = AsyncClient(host=settings.ollama_base_url, timeout=2.0)
        await client.list()
    except Exception:
        ollama_status = "unreachable"
    return {"status": "ok", "ollama": ollama_status}
```
`tests/test_health.py`'s existing assertion (`assert response.json() == {"status": "ok"}`, line 20) will need updating to check the `ollama` key too (see Test section below) — this is a **breaking change to an existing exact-match assertion**, flag it explicitly in the plan.

---

### `docker-compose.yml` (config) — add `ollama` service

**Analog:** itself — existing `mysql` service block (same file, lines 26-58)

**Pattern to copy** (healthcheck + internal-network + `depends_on` shape, lines 26-58, 72-77):
```yaml
mysql:
  image: mysql:8.4
  command: --innodb-ft-min-token-size=2
  env_file:
    - .env
  environment: ...
  volumes:
    - mysql_data:/var/lib/mysql
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "--password=${MYSQL_ROOT_PASSWORD}"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
  networks:
    - backend
  restart: unless-stopped

api:
  ...
  depends_on:
    mysql:
      condition: service_healthy
  networks:
    - backend
  restart: unless-stopped
```
Add an `ollama` service in the same block style — **do not** add a `ports:` mapping (mirrors the fact that `mysql` has none — internal-network-only convention, confirmed by the file's own header comment at lines 4-8 and RESEARCH.md's Security Domain note). Per RESEARCH.md Pitfalls 2-3 (verified independently, HIGH confidence): use `test: ["CMD", "ollama", "list"]` (not `curl` — image doesn't ship it) and the top-level `mem_limit: 4g` key (not `deploy.resources.limits.memory`, which plain `docker compose up` silently ignores). Add `OLLAMA_NUM_PARALLEL=1` / `OLLAMA_MAX_LOADED_MODELS=1` env vars per Common Pitfall 6. Extend `api`'s `depends_on` to also require `ollama: condition: service_healthy`, following the exact same key shape already used for `mysql` (lines 72-74).

---

### `alembic/versions/0006_add_note_summary.py` (migration)

**Analog:** `alembic/versions/0003_add_user_id_to_notes.py` (single nullable/simple `add_column` on `notes`, no new table — closer structural match than `0005_add_collections.py` which creates two tables)

**Migration-head chain to confirm:** current head is `0005_add_collections` (`revision = "0005_add_collections"`, confirmed by reading the file directly) — the new migration's `down_revision` **must** be `"0005_add_collections"`.

**Pattern to copy** (`0003_add_user_id_to_notes.py`, full file structure, lines 20-30, 33-49, 66-69 — note this example is more complex than needed since it also added a FK/index/TRUNCATE; the *shape* to copy is the revision header + a single `op.add_column`/`op.drop_column` pair):
```python
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0006_add_note_summary"
down_revision: str | Sequence[str] | None = "0005_add_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="AI-generated summary (Phase 5, D-02)",
        ),
    )


def downgrade() -> None:
    op.drop_column("notes", "summary")
```
This is much simpler than `0003`'s TRUNCATE+FK+index sequence (that migration's complexity came from adding a NOT NULL FK column to a populated table — not applicable here since `summary` is nullable with no FK). Match `0005_add_collections.py`'s revision-string convention (descriptive slug, not a random hash — both `0003` and `0005` use this style; the one legacy exception is `d51191e92276_create_notes_table.py`, the original auto-generated Phase-1 migration, which predates the slug convention and should NOT be imitated).

---

### `tests/conftest.py` (test fixtures) — add `FakeLLMProvider` + override fixture

**Analog:** itself — existing `client` fixture's `get_db` override pattern (same file, lines 110-127)

**Pattern to copy** (lines 110-127):
```python
@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:
    """AsyncClient with the test DB session injected via dependency override."""

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
```
RESEARCH.md's Code Examples § "Test fixtures — fake LLMProvider" (lines 506-537 of 05-RESEARCH.md) already provides the exact `FakeLLMProvider` class + `fake_llm_provider` + `ai_client` fixtures matching this override shape — use as written. Import `get_llm_provider` from `app.core.dependencies` the same way `get_db` is already imported at the top of `conftest.py` (line 30). Note the existing `client` fixture calls `app.dependency_overrides.clear()` at teardown (line 126) — if `ai_client` layers `get_llm_provider` on top of the `client` fixture's override (rather than being fully independent), ensure the override is set/cleared symmetrically so it doesn't leak into unrelated tests, matching how `user_a_client`/`user_b_client` already share one `session` override safely (see the explicit note at lines 325-327 in `conftest.py` about shared-override safety).

---

### `tests/test_ai.py` (new test file)

**Analog:** `tests/test_tags.py` (note-scoped POST with ownership 401/403/404 cases — same endpoint shape as `/ai/summarize` and `/ai/suggest-tags`)

Structure `test_ai.py` the same way `test_tags.py` is structured (fixtures: `auth_client`, `user_a_client`/`user_b_client` for the cross-owner 403 case, a plain unauthenticated client for 401) — RESEARCH.md's Code Examples § "Test asserting zero real calls + correct behavior" (lines 542-565 of 05-RESEARCH.md) already has two full test functions (`test_summarize_persists_and_uses_mock_only`, `test_ollama_down_returns_503`) — use these as the base and add the remaining cases from D-10's coverage list: suggest-tags-returns-list, retry-then-succeeds, and per-user ownership 403/404 (reuse `user_a_client`/`user_b_client` from `conftest.py` exactly as `tests/test_phase4_isolation.py` / `tests/test_notes_isolation.py` already do for the Notes/Tags domains).

---

### `tests/test_health.py` (modified)

**Analog:** itself (same file, full content — 21 lines)

**Current exact-match assertion to update** (line 20):
```python
assert response.json() == {"status": "ok"}
```
Must become an assertion that also checks the new `ollama` key is present, e.g. `assert response.json()["status"] == "ok"` and `assert "ollama" in response.json()` — plus a new test case exercising the "Ollama unreachable → still 200, degraded" path (requires overriding whatever internal client `health_check` uses, or accepting that this specific case is only meaningfully testable if the health probe itself is injectable — flag this as an open implementation question for the planner: either make the Ollama client construction in `health.py` go through `get_llm_provider`-style DI so it's overridable in tests, or accept that the "Ollama down" health branch is only exercised by the AI 503 tests in `test_ai.py`, not `test_health.py` directly).

## Shared Patterns

### Ownership / 404-vs-403 (all `app/ai/` endpoints)
**Source:** `app/notes/service.py::NoteService.get_or_404_owned` (lines 44-67)
**Apply to:** `AIService.summarize()` and `AIService.suggest_tags()` — inject the real `NoteService` into `AIService` and call `note_service.get_or_404_owned(note_id, current_user)` directly. Do **not** copy the check a third time the way `TagService` did (lines 33-50) — RESEARCH.md's own `AIService` example already does this correctly via constructor injection.
```python
note = await self._repo.get_by_id(note_id)
if note is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
if note.user_id != current_user.id:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")
return note
```

### Service-layer-only `HTTPException` (all new AI code)
**Source:** `app/notes/service.py` lines 100-107, `app/tags/service.py` lines 33-50
**Apply to:** `app/ai/service.py` — the router and provider must never raise `HTTPException` directly; the provider (`app/ai/providers/ollama.py`) raises plain `ConnectionError`/`httpx.TimeoutException`/`ollama.ResponseError`, and only `AIService._safe_complete` translates those to `HTTPException(503, ...)`.

### FastAPI dependency-override test seam
**Source:** `app/core/dependencies.py::get_db` + `tests/conftest.py::client` fixture (lines 110-127)
**Apply to:** `get_llm_provider` — same mechanism (`app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider`), giving `FakeLLMProvider` a zero-network guarantee identical to how `get_db` gives the test suite a zero-real-MySQL-connection guarantee outside the one testcontainer.

### `Settings` with `extra="ignore"` (config additions)
**Source:** `app/core/config.py` lines 9-17
**Apply to:** New `ollama_base_url` / `ollama_chat_model` / `ollama_timeout_seconds` / `ollama_max_retries` fields — add in the same grouped-comment style as the existing `# Database` / `# JWT` sections; no new validator needed (unlike JWT's secret-strength guard) since there's no secret to protect.

### Migration chain discipline
**Source:** `alembic/versions/0005_add_collections.py` (`down_revision = "0004_add_tags"`) and `0003_add_user_id_to_notes.py` (`down_revision = "a1b2c3d4e5f6"`)
**Apply to:** `0006_add_note_summary.py` must set `down_revision = "0005_add_collections"` — this is the current head, confirmed by directly reading the file (no other migration declares a `down_revision` pointing past `0005`).

### Docker Compose internal-network-only service
**Source:** `docker-compose.yml` `mysql` service (lines 26-58) — no `ports:` mapping, `networks: [backend]`, `healthcheck` + `depends_on: condition: service_healthy`
**Apply to:** New `ollama` service — same shape, swap `mysqladmin ping` for `ollama list` (curl unavailable in the image, RESEARCH.md Pitfall 2) and `mem_limit: 4g` instead of no memory constraint (RESEARCH.md Pitfall 3 — `deploy.resources.limits.memory` is silently ignored under plain `docker compose up`).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/ai/providers/protocol.py` | utility (Protocol interface) | transform | First `Protocol`-based interface in the codebase — no existing abstraction layer to copy; use RESEARCH.md Pattern 1 verbatim (fully worked, cited to official `ollama-python` source) |
| `app/ai/providers/ollama.py` | service (external client wrapper) | request-response (outbound to sibling container) | First outbound-HTTP client to a sibling Docker service (mysql access goes through SQLAlchemy, not a hand-rolled client) — use RESEARCH.md Pattern 2 verbatim, including the `tenacity` retry decorator shape |
| `app/ai/prompts.py` | utility (prompt templates) | transform | No prior LLM-prompting code exists in this codebase at all — write fresh per D-03/D-05 (2-3 sentence summary prompt; JSON-tag-list prompt), following RESEARCH.md's Security Domain note about wrapping note content in explicit prompt delimiters |

## Metadata

**Analog search scope:** `app/notes/`, `app/tags/`, `app/collections/`, `app/search/`, `app/core/`, `app/api/`, `app/main.py`, `alembic/versions/`, `tests/conftest.py`, `tests/test_tags.py`, `tests/test_health.py`, `docker-compose.yml`, `pyproject.toml`
**Files scanned:** 18 read in full (all under 300 lines each — single-pass reads, no re-reads)
**Pattern extraction date:** 2026-07-05

---
*Phase: 5-Local AI (Ollama)*
*Patterns mapped: 2026-07-05*
