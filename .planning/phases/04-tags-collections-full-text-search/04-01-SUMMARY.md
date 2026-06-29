---
phase: 04-tags-collections-full-text-search
plan: 01
subsystem: tags
tags: [tags, many-to-many, ORG-01, selectinload, migration, mysql, fastapi]
dependency_graph:
  requires: [phase-03-auth-per-user-data-isolation]
  provides: [GET /tags, "POST /notes/{id}/tags", "DELETE /notes/{id}/tags/{name}", note_tags, Tag ORM, NoteRead.tags]
  affects: [app/notes/models.py, app/notes/schemas.py, app/notes/repository.py, tests/conftest.py]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy many-to-many via Table() + relationship(secondary=...)
    - selectinload(Note.tags) on every Note-returning query
    - find-or-create SAVEPOINT (begin_nested) for race-condition safety
    - get_by_id re-fetch after create/update instead of session.refresh()
key_files:
  created:
    - alembic/versions/0004_add_tags.py
    - app/tags/__init__.py
    - app/tags/models.py
    - app/tags/schemas.py
    - app/tags/repository.py
    - app/tags/service.py
    - app/tags/router.py
    - tests/test_tags.py
  modified:
    - tests/conftest.py
    - app/notes/models.py
    - app/notes/schemas.py
    - app/notes/repository.py
    - app/core/dependencies.py
    - app/main.py
decisions:
  - "Two migrations chosen (0004 tags, 0005 collections) instead of one — keeps vertical slices self-contained"
  - "TagRead schema created in Task 2 (not Task 3) to resolve NoteRead forward reference at runtime"
  - "create/update use get_by_id re-fetch instead of session.refresh() — refresh expires Note.tags relationship"
metrics:
  duration_minutes: 45
  completed_date: "2026-06-29"
  tasks_completed: 3
  files_touched: 14
---

# Phase 4 Plan 01: Tags Vertical Slice Summary

**One-liner:** Tags domain (ORG-01) implemented as a vertical slice — find-or-create on attach, normalized names, per-user isolation, SAVEPOINT-safe concurrent inserts, and selectinload on all Note queries.

## What Was Built

Delivered the full Tags vertical slice:

- **Migration 0004** (`alembic/versions/0004_add_tags.py`): creates `tags` (UNIQUE(user_id, name)) and `note_tags` (composite PK, CASCADE FKs) tables; drops and re-adds `ft_notes_content` FULLTEXT index to reindex at `innodb_ft_min_token_size=2` (D-11).

- **Tag ORM model** (`app/tags/models.py`): `Tag(Base)` with `UniqueConstraint("user_id", "name", name="uq_user_tag")` in tuple-form `__table_args__` (required when mixing constraints + dict kwargs).

- **Schema foundation** (`app/tags/schemas.py`, `app/notes/schemas.py`, `app/notes/models.py`): `TagCreate` + `TagRead`; `NoteRead` extended with `tags: list[TagRead] = []`; `note_tags` association Table and `tags: Mapped[list[Tag]]` relationship on Note.

- **Repository** (`app/tags/repository.py`): `find_or_create` (normalize → SELECT → INSERT inside `begin_nested()` SAVEPOINT → re-SELECT on IntegrityError); `list_by_user`; `attach`/`detach` via ORM collection append/remove + flush.

- **Service** (`app/tags/service.py`): `get_or_404_owned` (mirrors NoteService, enforces T-04-iso); `attach_tag` (find-or-create + attach + get_by_id re-fetch for fresh selectinload); `detach_tag` (ownership + tag presence check → 404 if absent).

- **Router** (`app/tags/router.py`): `GET /tags`, `POST /notes/{note_id}/tags` (200), `DELETE /notes/{note_id}/tags/{name}` (204) — registered with no prefix in `app/main.py`.

- **Test coverage** (`tests/test_tags.py`): 8 integration tests — attach (200 + tags array), idempotency, normalization, list tags, detach (204), 401 unauthenticated, 404 missing note, cross-user isolation.

- **conftest.py**: `mysql_container` fixture updated to `.with_command("--innodb-ft-min-token-size=2")` (D-11).

## Verification

- `uv run alembic upgrade head` — applied 0004 cleanly
- `uv run pytest tests/ -q` — **80 tests passed, 0 failed** (full suite including test_tags.py)
- `uv run ruff check app/tags app/notes app/main.py app/core/dependencies.py` — clean
- `uv run mypy app/tags` — clean (6 source files, no issues)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] session.refresh() exposes MissingGreenlet on Note.tags**

- **Found during:** Task 3 integration test run (test_create_note_returns_201 failed)
- **Issue:** `NoteRepository.create()` and `update()` called `session.refresh(note)` after commit. In SQLAlchemy 2.x async, `refresh()` expires ALL attributes including the `tags` relationship. Accessing `note.tags` (now expired) outside an async context in Pydantic serialization raises `MissingGreenlet: greenlet_spawn has not been called`.
- **Fix:** Replaced `session.refresh(note)` with `await self.get_by_id(note.id)` in both `create()` and `update()`. `get_by_id` uses `selectinload(Note.tags)` so the relationship is eagerly loaded and always safe to serialize.
- **Files modified:** `app/notes/repository.py`
- **Commits:** 29e0570

**2. [Rule 2 - Missing Critical Functionality] TagRead schema moved to Task 2**

- **Found during:** Task 2 schema foundation
- **Issue:** Plan placed `app/tags/schemas.py` in Task 3. However, `app/notes/schemas.py` imports `TagRead` directly — if `TagRead` is undefined at import time, Pydantic v2 raises `PydanticUserError` on `NoteRead` model construction, breaking all note endpoints.
- **Fix:** Created `app/tags/schemas.py` (TagCreate + TagRead) in Task 2 as part of the schema foundation. Task 3 required no changes to this file.
- **Files created:** `app/tags/schemas.py`
- **Commits:** 19f5c1b

## Threat Model Compliance

All T-04-* mitigations implemented as planned:
- **T-04-iso:** `get_or_404_owned` in TagService enforces 403 (wrong owner) / 404 (missing); all tag queries scoped to `WHERE user_id = current_user.id`; verified by `test_tag_isolation`.
- **T-04-01:** `UNIQUE(user_id, name)` + SAVEPOINT (`begin_nested`) re-selects on `IntegrityError` — session state never corrupted.
- **T-04-02:** `GET /tags` filters to caller's `user_id` — no global tag IDs exposed.
- **T-04-03:** `get_current_user` JWT dependency (401) inherited from Phase 3, applied to all 3 tag endpoints.
- **T-04-SC:** No new packages installed this plan.

## Known Stubs

None. All endpoints return real data from MySQL.

## Self-Check: PASSED

- `alembic/versions/0004_add_tags.py` — FOUND
- `app/tags/models.py` — FOUND
- `app/tags/repository.py` — FOUND
- `app/tags/router.py` — FOUND
- `tests/test_tags.py` — FOUND
- Commits fa1a25e, 19f5c1b, 29e0570 — all in git log
- 80 tests passed, 0 failed
