# Phase 2: Database + API Skeleton - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a **fully working Note CRUD REST API backed by async MySQL, running in Docker** — the first real application feature of the project (a vertical MVP slice).

In scope:
- A `notes` table managed by **Alembic migrations** (no `Base.metadata.create_all()`), `utf8mb4` charset
- Async data access via **SQLAlchemy 2.0 + asyncmy**
- Full CRUD endpoints for notes (create, read-one, list, update, delete) exposed through auto-generated **Swagger/OpenAPI** at `/docs`
- `GET /notes` with **pagination, sorting, and filtering**
- A **pytest** suite covering core note endpoints against a **real MySQL** (no DB mocks)
- `docker compose up` starts **api + mysql**, with only the api port (8000) exposed to the host

Maps to requirements: **NOTE-01, NOTE-02, NOTE-03, NOTE-04, API-01, API-02, API-03, OPS-01**.

Out of scope (later phases): authentication / per-user data isolation (Phase 3), tags & collections & full-text search (Phase 4), local/cloud AI (Phases 5–6), CI pipeline & prod environment (Phase 7). **No auth at this phase** — endpoints are open.

</domain>

<decisions>
## Implementation Decisions

### Note Data Model
- **D-01:** Primary key is **BIGINT autoincrement** (not UUID) — simplest, standard, good MySQL learning; easy to reference from future tags/collections tables.
- **D-02:** Note fields are **`content` (required, TEXT)** + **`source_url` (optional, nullable)** only. **No separate `title` field** — matches roadmap scope ("text content and optional source URL") and keeps the slice thin.
- **D-03:** Both **`created_at` and `updated_at`** timestamp columns, server-managed (DB `DEFAULT CURRENT_TIMESTAMP` / `ON UPDATE CURRENT_TIMESTAMP` or SQLAlchemy equivalent). `updated_at` enables sort-by-recently-modified.
- **D-04:** `DELETE /notes/{id}` is a **hard delete** (row removed, returns 204). No soft-delete / `deleted_at` flag this phase.

### List Endpoint Contract (`GET /notes`)
- **D-05:** Pagination via **`?page=` (1-based) and `?size=`**. Default `size=20`, **max `size=100`** — a request over the max returns **422**.
- **D-06:** Response is a **JSON envelope: `{ items, total, page, size, pages }`** (page of notes + pagination metadata), not a bare array.
- **D-07:** Sorting via **`?sort=`**. Default **`-created_at`** (newest first). Allowed fields: **`created_at`, `updated_at`**; a leading `-` means descending (e.g. `?sort=created_at` = oldest first). Unknown sort field → **422**.
- **D-08:** Filtering via **`?filter=`** = **case-insensitive substring match on `content`** (SQL `LIKE %term%`, utf8mb4 case-insensitive collation). This is simple keyword narrowing — real FULLTEXT search is SRCH-01 (Phase 4).
- **D-09:** Status codes per success criteria: **200** (read/list/update), **201** (create), **204** (delete), **404** (note not found), **422** (validation / bad query params).

### Code Layout & Architecture
- **D-10:** **Domain-per-folder** layout per `research/ARCHITECTURE.md`: a new **`app/notes/`** package containing `router.py`, `schemas.py`, `models.py`, `service.py`, `repository.py`.
- **D-11:** **Remove the empty Phase-1 layer folders** `app/services/` and `app/repositories/` (they were placeholders; domain-per-folder supersedes them). **Keep `app/api/health.py` as-is** — it's an infra endpoint, not a domain, and works; don't churn it.
- **D-12:** **Keep a thin `NoteService`** layer (Router → Service → Repository) even though CRUD has no business logic yet — establishes the pattern that Phase 3+ (auth scoping, AI orchestration) will need. All SQL lives in `NoteRepository`; routers hold zero business logic.
- **D-13:** Pydantic v2 **separate `NoteCreate` / `NoteUpdate` / `NoteRead` schemas** (per ARCHITECTURE.md), with `model_config = ConfigDict(from_attributes=True)` for ORM mode on read.

### Database & Migrations
- **D-14:** Async engine + `async_sessionmaker` + `DeclarativeBase` live in **`app/core/database.py`**; a `get_session` FastAPI dependency yields an `AsyncSession` per request. Engine lifecycle (dispose) wired via FastAPI **lifespan** in `app/main.py`.
- **D-15:** **Alembic with async `env.py`** manages the schema. `alembic upgrade head` must run in the container and create all tables with `utf8mb4`. **`Base.metadata.create_all()` must be absent from app startup.**

### Test Strategy
- **D-16:** pytest gets a real MySQL via **testcontainers-python** — an ephemeral `mysql:8.4` container spun up per test session and torn down after. Same code path works locally and in Phase 7 GitHub Actions CI. Adds a dev dependency and requires Docker running.
- **D-17:** The test database schema is built by running **`alembic upgrade head`** against the test DB (not `metadata.create_all`) — verifies migrations actually work (success criterion 4) and matches production exactly.
- **D-18:** Test isolation is **transaction-per-test, rolled back at teardown** — fast, fully isolated, DB stays clean. Standard async SQLAlchemy testing pattern.
- **D-19:** Error responses use **FastAPI defaults** — `{"detail": "..."}` for 404 (`HTTPException`) and FastAPI's built-in 422 validation body. No custom error envelope this phase.

### Docker
- **D-20:** Add a **`mysql:8.4` service** to `docker-compose.yml` (pinned version), on the internal Docker network. **Only the api port (8000) is exposed to the host** — mysql stays internal. Use a **healthcheck on mysql + `depends_on: condition: service_healthy`** so the api waits for the DB. MySQL credentials come from `.env` (`MYSQL_*`, `DATABASE_URL` already present in `.env.example` from Phase 1). Persist data via a named volume.

### Claude's Discretion
- Exact Alembic setup details (autogenerate the first migration vs hand-write it — either is fine as long as it produces the `utf8mb4` `notes` table and `create_all` is absent).
- DB session dependency wiring specifics and lifespan implementation details.
- Healthcheck command/interval specifics for the mysql service.
- Default page-size clamping vs rejecting (D-05 says reject over-max with 422; lower bounds and `page<1` handling are Claude's discretion — reasonable validation expected).
- Test fixture organization (`conftest.py` structure, session vs function scope for the container).
- Whether the notes table gets an index on `created_at` (recommended for sort) — Claude's discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — product context, constraints, locked stack decisions
- `.planning/REQUIREMENTS.md` — NOTE-01..04, API-01..03, OPS-01 are the requirements in scope this phase
- `.planning/ROADMAP.md` §"Phase 2: Database + API Skeleton" — goal and the 6 success criteria this phase is judged against
- `.planning/STATE.md` §Decisions — locked stack (asyncmy not aiomysql, python:3.12-slim, Python 3.12) and the "Alembic-not-create_all" / `utf8mb4` flags

### Research
- `.planning/research/ARCHITECTURE.md` — domain-per-folder layering (Router → Service → Repository), `app/notes/{router,schemas,models,service,repository}.py` layout, `app/core/database.py` (async engine/session/Base), separate Pydantic Create/Update/Read schemas, MySQL 8.4 + InnoDB + utf8mb4
- `.planning/research/STACK.md` — SQLAlchemy 2.x async, asyncmy DSN (`mysql+asyncmy://...?charset=utf8mb4`), Alembic async env.py, pytest-asyncio + httpx AsyncClient testing
- `.planning/research/PITFALLS.md` — Alembic-not-create_all, utf8mb4, MySQL pinned (mysql:8.x not MariaDB), async engine pitfalls, secrets-at-runtime

### Phase 1 carry-forward
- `.planning/phases/01-repo-foundation/01-CONTEXT.md` — D-07 (structured skeleton intent), D-12 (Docker base image, mysql deferred to Phase 2), `.env.example` shape

### Existing code (integration targets)
- `app/main.py` — FastAPI app assembly; router registration + lifespan goes here
- `app/core/config.py` — `pydantic-settings` `Settings` (currently `extra="ignore"`); `DATABASE_URL` etc. get consumed here this phase
- `app/api/health.py` — the established `APIRouter` pattern to mirror for the notes router
- `tests/test_health.py` — the established httpx `ASGITransport` async test pattern to extend
- `.env.example` — already contains `MYSQL_*` and `DATABASE_URL` placeholders (from Phase 1 D-10)

No user-referenced external docs/ADRs were introduced during discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/api/health.py`**: the `APIRouter()` + async handler + typed return pattern — mirror it for `app/notes/router.py`.
- **`tests/test_health.py`**: in-process `httpx.AsyncClient(transport=ASGITransport(app=app))` pattern — the basis for note endpoint tests (extended with a real MySQL session + transaction rollback).
- **`app/core/config.py`**: `Settings(BaseSettings)` already loads `.env`; add `DATABASE_URL` consumption here. `extra="ignore"` already tolerates unused future vars.
- **`pyproject.toml`**: `asyncio_mode = "auto"` and `testpaths = ["tests"]` already configured; new deps (sqlalchemy, asyncmy, alembic) and dev dep (testcontainers) get added here.

### Established Patterns
- **Domain-per-folder** is now the convention (this phase establishes it in code for the first time): `app/notes/` holds router/schemas/models/service/repository.
- **Router → Service → Repository** with zero business logic in routers, all SQL in repositories.
- **Secrets at runtime via `.env` / `env_file`** — never baked into images (carried from Phase 1).

### Integration Points
- `app/main.py` registers the notes router and owns the lifespan that disposes the async engine.
- `docker-compose.yml` gains a `mysql:8.4` service (internal network, healthcheck); api `depends_on` it.
- `app/core/database.py` is new and becomes the shared async DB layer all future domains use.

</code_context>

<specifics>
## Specific Ideas

- This is an **MVP vertical slice** — deliver thin end-to-end working CRUD (DB → repository → service → router → Swagger), not horizontal layers built in isolation.
- The `docker compose up` → open `http://localhost:8000/docs` → create/list/update/delete a note flow must actually work end-to-end at the end of this phase (the README promise stays true).
- Tests must exercise **real migrations against real MySQL** — the point of the phase is to prove the DB + migrations + async stack genuinely work, not to mock them away.

</specifics>

<deferred>
## Deferred Ideas

- **Auth / per-user scoping** on notes (`user_id` FK, ownership checks) — Phase 3. Notes are user-agnostic this phase.
- **Tags, collections, FULLTEXT search** — Phase 4 (the `?filter=` substring match here is deliberately simpler than SRCH-01).
- **`title` field on notes** — could be added later if note-listing UX wants it (D-02 keeps it out for now).
- **Soft delete / trash / undo** — only if a future need appears (D-04 is hard delete).
- **Custom error envelope** (`{error:{code,message}}`) — deferred; FastAPI defaults this phase (D-19).
- **CI pipeline / prod compose override** — Phase 7. testcontainers (D-16) is chosen partly so the same test setup drops into Actions cleanly later.

None of the above is scope creep into Phase 2 — they are correctly sequenced into their own phases.

</deferred>

---

*Phase: 2-Database + API Skeleton*
*Context gathered: 2026-06-24*
