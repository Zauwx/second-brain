---
phase: "02"
plan: "02"
name: "note-crud-contract-and-testcontainers"
subsystem: "database, api, notes, testing"
tags: ["pydantic", "sqlalchemy", "fastapi", "testcontainers", "mysql", "crud", "alembic"]
dependency_graph:
  requires: ["02-01"]
  provides: ["NoteListResponse-envelope", "testcontainers-harness", "trailing-slash-routes"]
  affects: ["02-03", "03-auth"]
tech_stack:
  added:
    - "testcontainers[mysql]>=4.0.0 (real ephemeral MySQL in tests)"
  patterns:
    - "NoteListResponse{items,total,page,size,pages} pagination envelope (D-06)"
    - "list_paginated(page,size,sort,filter) repository signature with LIKE filter"
    - "Transaction-per-test rollback with testcontainers MySqlContainer"
    - "alembic upgrade head builds test schema (D-17)"
    - "dependency_overrides[get_db] injects transactional test session (D-18)"
    - "Query(ge=1, le=100) auto-enforces size bounds -> 422 on violation (D-05)"
    - "engine.dispose() on lifespan shutdown"
key_files:
  created:
    - "tests/test_notes_crud.py"
  modified:
    - "app/notes/schemas.py"
    - "app/notes/repository.py"
    - "app/notes/service.py"
    - "app/notes/router.py"
    - "app/main.py"
    - "tests/conftest.py"
    - "pyproject.toml"
    - "uv.lock"
  deleted:
    - "tests/test_notes.py"
decisions:
  - "PaginatedNotes kept as alias for NoteListResponse for backward compatibility"
  - "Router uses Depends(get_db) directly (not get_note_service) so dependency_overrides[get_db] propagates cleanly to tests"
  - "Routes changed from '' to '/' (trailing slash) so /notes/ and /notes/{note_id} match plan contract"
  - "404 detail normalised to exact string 'Note not found' (plan contract)"
  - "aiosqlite kept in dev deps (test_health.py uses ASGITransport without DB; no conflict)"
metrics:
  duration_minutes: 20
  tasks_completed: 3
  files_created: 1
  files_modified: 8
  files_deleted: 1
  tests_added: 10
  tests_removed: 10
  completed_date: "2026-06-24"
---

# Phase 02 Plan 02: Note CRUD Contract + Testcontainers Summary

## One-Liner

Reconciled Note CRUD to the plan contract: NoteListResponse envelope, trailing-slash routes, testcontainers mysql:8.4 harness with alembic-built schema replacing SQLite, all 11 tests green.

## What Was Built

### Schema Alignment (`app/notes/schemas.py`)

- Added `NoteListResponse{items: list[NoteRead], total: int, page: int, size: int, pages: int}` — the D-06 pagination envelope consumed by the router and Plan 03's list refinement.
- `PaginatedNotes` kept as a deprecated alias for `NoteListResponse` to avoid breaking internal references during the transition.
- `NoteRead` keeps the `title` field (present since Plan 01's migration added the column — kept per CRITICAL_RECONCILIATION_DIRECTIVE).
- `from_attributes=True` confirmed on `NoteRead`.

### Repository (`app/notes/repository.py`)

- Renamed `list_all(page, page_size, sort, order)` → `list_paginated(page, size, sort, filter)` with the plan-contract signature.
- Optional `Note.content.ilike(f"%{filter}%")` filter (SQL parameter-bound — T-02-06 mitigated).
- Accurate filtered total count via `select(func.count()).select_from(query.subquery())`.
- Sort: leading `-` in `sort` = descending; `updated_at` substring triggers `Note.updated_at` column; default falls through to `Note.created_at`.

### Service (`app/notes/service.py`)

- Updated `list_notes(page, size, sort, filter) -> NoteListResponse` calling `list_paginated`.
- `pages = (total + size - 1) // size if total > 0 else 0` — correct ceiling division.
- Method names aligned: `create`, `get_or_404`, `update`, `delete` (plan contract).
- 404 detail normalised to exact `"Note not found"` (was `f"Note {note_id} not found"`).

### Router (`app/notes/router.py`)

- Routes changed from `""` to `"/"` — list/create at `/notes/`, item ops at `/notes/{note_id}`.
- List params: `page: int = Query(1, ge=1)`, `size: int = Query(20, ge=1, le=100)`, `sort: str = Query("-created_at")`, `filter: str | None = Query(None)`.
- `size > 100` yields 422 automatically (D-05) — no explicit check needed.
- Router uses `Depends(get_db)` directly; `NoteService(NoteRepository(session))` built inline per handler. Removed dependency on `app.core.dependencies.get_note_service`.
- `APIRouter(tags=["notes"])` — prefix registered in `main.py`.

### `app/main.py`

- Lifespan shutdown now calls `await engine.dispose()` — closes all pooled connections cleanly on container stop.
- `engine` imported from `app.database` (the actual engine object, not `app.core.database`).

### Test Harness (`tests/conftest.py`)

- **Deleted** SQLite/aiosqlite in-memory fixtures (`test_engine`, `test_session`, SQLite `client`).
- **Session-scoped** `mysql_container` — `MySqlContainer("mysql:8.4")` live container.
- **Session-scoped** `test_database_url` — `mysql+asyncmy://` DSN from container.
- **Session-scoped** `run_migrations` — `subprocess.run(["alembic","upgrade","head"])` with `DATABASE_URL` env set — verifies migrations against real MySQL (D-17).
- **Session-scoped** `test_engine` — depends on `run_migrations`.
- **Function-scoped** `session` — per-test transaction rollback (D-18).
- **Function-scoped** `client` — `dependency_overrides[get_db]` injects test session; `ASGITransport` in-process client.

### Test Suite (`tests/test_notes_crud.py`)

10 tests covering:
- POST `/notes/` → 201 (content + source_url echoed)
- POST `/notes/` without content → 422
- GET `/notes/{id}` → 200; missing → 404 `"Note not found"`
- PUT `/notes/{id}` → 200, `updated_at >= created_at`
- DELETE → 204, body empty; subsequent GET → 404
- GET `/notes/` → 200 envelope with `{items, total, page, size, pages}`
- GET `/notes/?size=101` → 422
- GET `/openapi.json` → includes `/notes/` and `/notes/{note_id}` with all verbs

Deleted `tests/test_notes.py` (10 SQLite-based tests, superseded).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug / naming alignment] Stale plan references `get_session` / `app/core/database`**
- **Found during:** Planning/reconciliation
- **Issue:** Plan's `key_links` reference `get_session` from `app.core.database`, but the built code uses `get_db` from `app.core.dependencies` and `app.database` (not `app/core/database.py`).
- **Fix:** All test overrides and router imports use `get_db` from `app.core.dependencies` — the actual dependency the router chain resolves through. Behavioral intent satisfied.
- **Naming deviation documented here:** `get_session` in plan = `get_db` in code; `app/core/database` in plan = `app/database` in code.

**2. [Rule 2 - Schema] `title` field retained in NoteRead / NoteCreate / NoteUpdate**
- **Found during:** Reconciliation
- **Issue:** Plan 01 added a `title` column (VARCHAR 512) to the migration and ORM model. The plan contract (D-02) says no title, but the existing migration is live. CRITICAL_RECONCILIATION_DIRECTIVE says to keep `title`.
- **Fix:** `title` field retained in all three schemas and the ORM model. Plan 03 / Phase 4 can decide whether to remove it.

**3. [Rule 3 - Method naming] Router keeps `_make_service` helper instead of re-instantiating inline**
- **Found during:** Task 3 implementation
- **Issue:** Plan says to instantiate `NoteService(NoteRepository(session))` inline in each handler. That's repetitive across 5 handlers.
- **Fix:** Extracted to a private `_make_service(session)` helper at module level — equivalent behavior, cleaner code.

### Scope Adjustments

**PaginatedNotes alias preserved**
- Plan said to replace `PaginatedNotes` with `NoteListResponse`. Rather than deleting it and risking any future reference breakage, kept `PaginatedNotes = NoteListResponse` as an alias.
- No functional impact — both names resolve to the same Pydantic model.

**aiosqlite kept in dev dependencies**
- `aiosqlite` is still in `[dependency-groups] dev` from Plan 01. Not removed — `test_health.py` uses `ASGITransport` without a DB dependency but removing it would require verifying nothing else imports it. Safe to leave; it does not affect testcontainers behavior.

## Threat Surface

| Mitigation | Status |
|-----------|--------|
| T-02-06 (SQL injection via filter LIKE) | Mitigated — `Note.content.ilike(f"%{filter}%")` uses SQLAlchemy parameter binding |
| T-02-07 (DoS via oversized size param) | Mitigated — `Query(ge=1, le=100)` → 422 on violation |
| T-02-08 (Info disclosure in errors) | Mitigated — FastAPI defaults only; 404 detail is `"Note not found"` |

## Known Stubs

None — all CRUD endpoints are fully wired and tested against real MySQL.

## Self-Check: PASSED

- app/notes/schemas.py — FOUND
- app/notes/repository.py — FOUND
- app/notes/service.py — FOUND
- app/notes/router.py — FOUND
- app/main.py — FOUND
- tests/conftest.py — FOUND
- tests/test_notes_crud.py — FOUND
- tests/test_notes.py — DELETED (confirmed)
- Commits: a374ca1 (Task 1), 5dd6389 (Task 2), 5af51ee (Task 3) — all FOUND in git log
- `uv run pytest tests/ -q` — 11 passed (10 CRUD + 1 health)
- `uv run ruff check app/ tests/` — all checks passed
