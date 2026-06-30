---
phase: 04-tags-collections-full-text-search
plan: 03
subsystem: collections
tags: [collections, many-to-many, ORG-03, ORG-04, migration, per-user-isolation, fastapi]
dependency_graph:
  requires: [04-01-tags-vertical-slice]
  provides: [GET /collections/, "POST /collections/", "POST /collections/{id}/notes", "DELETE /collections/{id}/notes/{note_id}", "GET /collections/{id}/notes", Collection ORM, note_collections]
  affects: [app/notes/models.py, app/core/dependencies.py, app/main.py]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy many-to-many via Table() + relationship(secondary=...) — same as note_tags
    - selectinload(Collection.notes) on get_by_id to prevent MissingGreenlet in add/remove
    - get_or_404_owned 404/403 ownership pattern — copied from NoteService/TagService
    - NoteListResponse envelope reused verbatim for GET /collections/{id}/notes
    - Bottom-of-file side-effect import (_Collection) to register Collection with mapper registry before configure_mappers()
key_files:
  created:
    - alembic/versions/0005_add_collections.py
    - app/collections/__init__.py
    - app/collections/models.py
    - app/collections/schemas.py
    - app/collections/repository.py
    - app/collections/service.py
    - app/collections/router.py
    - tests/test_collections.py
  modified:
    - app/notes/models.py
    - app/core/dependencies.py
    - app/main.py
decisions:
  - "selectinload(Collection.notes) in get_by_id — always load notes to avoid MissingGreenlet when add_note/remove_note accesses collection.notes in async context"
  - "Collection imported as _Collection at bottom of app/notes/models.py (side-effect import for mapper registry) + TYPE_CHECKING for mypy — avoids circular import while satisfying both SQLAlchemy runtime resolution and static analysis"
  - "overlaps='notes'/'collections_rel' added to both sides of the bidirectional relationship to suppress SQLAlchemy 'copies column' SAWarning"
metrics:
  duration_minutes: 20
  completed_date: "2026-06-29"
  tasks_completed: 3
  files_touched: 11
---

# Phase 4 Plan 03: Collections Vertical Slice Summary

**One-liner:** Collections domain (ORG-03, ORG-04) implemented as a vertical slice — per-user named collections, many-to-many note membership via `note_collections`, 403/404 ownership contract, and `NoteListResponse` envelope for `GET /collections/{id}/notes`.

## What Was Built

Delivered the full Collections vertical slice:

- **Migration 0005** (`alembic/versions/0005_add_collections.py`): chains from `0004_add_tags`; creates `collections` (UNIQUE(user_id, name) named `uq_user_collection`, InnoDB/utf8mb4) and `note_collections` (composite PK, CASCADE FKs on both sides).

- **Collection ORM model** (`app/collections/models.py`): `Collection(Base)` with tuple-form `__table_args__` (UniqueConstraint + dict), `Collection.notes` relationship using `secondary="note_collections"` with `lazy="select"` and `overlaps="collections_rel"`.

- **Schema layer** (`app/collections/schemas.py`): `CollectionCreate` (name, min_length=1, max_length=255), `CollectionRead` (from_attributes), `NoteAddBody` (note_id: int). `NoteListResponse` from `app.notes.schemas` reused without duplication.

- **Notes model extension** (`app/notes/models.py`): added `note_collections` association Table (string FK refs, CASCADE, InnoDB) and `Note.collections_rel` relationship (`"Collection"`, secondary=note_collections, overlaps="notes"); bottom-of-file `_Collection` side-effect import ensures `Collection` is in SQLAlchemy's class registry before `configure_mappers()`.

- **Repository** (`app/collections/repository.py`): `get_by_id` with `selectinload(Collection.notes)` (prevents MissingGreenlet on add/remove), `create` (add/commit/refresh), `list_by_user`, `add_note`/`remove_note` (ORM append/remove + commit), `list_notes` (JOIN note_collections, double-scoped by collection_id + user_id, selectinload(Note.tags), paginated).

- **Service** (`app/collections/service.py`): `CollectionService` — `get_or_404_owned` (404 missing / 403 wrong owner, T-04-iso), `create`, `list_collections` (scoped to caller, T-04-06), `add_note` (verifies both collection and note ownership), `remove_note`, `list_notes` returning `NoteListResponse` envelope.

- **Router** (`app/collections/router.py`): `POST /` (201), `GET /` (list[CollectionRead]), `POST /{id}/notes` (204), `DELETE /{id}/notes/{note_id}` (204), `GET /{id}/notes` (NoteListResponse with page/size Query). Registered in `app/main.py` with `prefix="/collections"`.

- **Test coverage** (`tests/test_collections.py`): 6 integration tests — create (201), list own, list-notes envelope (items/total/pages), remove note (204 + disappears), many-to-many (same note in two collections), isolation (`test_collection_isolation`: 403 cross-user access, 404 missing collection, list isolation).

## Verification

- `uv run pytest tests/test_collections.py -q` — **6 passed, 0 failed**
- `uv run pytest tests/ -q` — **90 tests passed, 0 failed** (full suite, all prior tests unaffected)
- `uv run ruff check app/collections app/main.py app/core/dependencies.py` — clean
- `uv run mypy app/collections app/notes/models.py` — clean (7 source files, no issues)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MissingGreenlet when accessing Collection.notes in add_note/remove_note**

- **Found during:** Task 3 test run (`test_list_collection_notes_returns_envelope` failed)
- **Issue:** `CollectionRepository.add_note` accessed `collection.notes` (lazy-loaded, `lazy="select"`) outside an async context. SQLAlchemy 2.x async raises `MissingGreenlet: greenlet_spawn has not been called` when lazy-loading inside a synchronous attribute access path.
- **Fix:** Added `selectinload(Collection.notes)` to `CollectionRepository.get_by_id`. The collection fetched by `get_or_404_owned` now has `notes` eagerly loaded, so `collection.notes.append(note)` / `collection.notes.remove(note)` in `add_note`/`remove_note` never trigger a lazy load.
- **Files modified:** `app/collections/repository.py`
- **Commits:** 2891be2

**2. [Rule 1 - Bug] SQLAlchemy 'Collection' not in mapper registry — InvalidRequestError**

- **Found during:** Task 2 verification (`uv run pytest tests/test_notes_crud.py` failed)
- **Issue:** `Note.collections_rel` uses `relationship("Collection", ...)`. SQLAlchemy resolves `"Collection"` at mapper-configure time by searching the class registry. `app.collections.models` was not imported via the app startup path (no router registered yet), so `Collection` was absent from the registry.
- **Fix:** Added `from app.collections.models import Collection as _Collection  # noqa: F401` at the bottom of `app/notes/models.py` as a side-effect import. Also added `Collection` to `TYPE_CHECKING` for mypy. This pattern is safe: `app.collections.models` imports `Note` only under `TYPE_CHECKING` — no circular dependency.
- **Files modified:** `app/notes/models.py`
- **Commits:** aaad6fb

**3. [Rule 1 - Bug] SQLAlchemy SAWarning for overlapping bidirectional relationship**

- **Found during:** Task 2 test run (2 warnings in pytest output)
- **Issue:** `Collection.notes` and `Note.collections_rel` both manage writes to `note_collections` without declaring their overlap, causing SQLAlchemy to warn `relationship 'Collection.notes' will copy column notes.id to column note_collections.note_id, which conflicts with...`.
- **Fix:** Added `overlaps="collections_rel"` to `Collection.notes` and `overlaps="notes"` to `Note.collections_rel`.
- **Files modified:** `app/collections/models.py`, `app/notes/models.py`
- **Commits:** aaad6fb

## Threat Model Compliance

All T-04-* mitigations implemented as planned:
- **T-04-iso:** `get_or_404_owned` in CollectionService enforces 403 (wrong owner) / 404 (missing); `add_note` also verifies note ownership; `list_notes` double-scoped by collection_id + user_id; verified by `test_collection_isolation`.
- **T-04-06:** `list_by_user` scopes to caller; note listing double-scoped by user_id — no cross-user data exposure.
- **T-04-07:** `get_current_user` JWT dependency (401) inherited from Phase 3, applied to all 5 collection endpoints.
- **T-04-SC:** No new packages installed this plan.

## Known Stubs

None. All endpoints return real data from MySQL.

## Threat Flags

None. No new network surfaces beyond the planned `/collections` prefix. All endpoints are behind `get_current_user`.

## Self-Check: PASSED

- `alembic/versions/0005_add_collections.py` — FOUND
- `app/collections/models.py` — FOUND
- `app/collections/repository.py` — FOUND
- `app/collections/router.py` — FOUND
- `app/collections/service.py` — FOUND
- `app/collections/schemas.py` — FOUND
- `tests/test_collections.py` — FOUND
- Commits ac38d15 (test), aaad6fb (schema), 2891be2 (API) — all in git log
- 90 tests passed, 0 failed
