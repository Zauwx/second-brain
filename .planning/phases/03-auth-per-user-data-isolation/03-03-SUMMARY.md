---
phase: 03-auth-per-user-data-isolation
plan: "03"
subsystem: notes
tags: [per-user-isolation, ownership, fk-migration, 403-vs-404, tdd, auth, jwt]
dependency_graph:
  requires: [03-01 (User model, auth domain), 03-02 (get_current_user dependency)]
  provides: [notes.user_id FK migration, get_or_404_owned ownership check, protected note endpoints, isolation test suite]
  affects: [app/notes/models.py, app/notes/schemas.py, app/notes/repository.py, app/notes/service.py, app/notes/router.py, alembic/versions/0003_add_user_id_to_notes.py, tests/]
tech_stack:
  added: []
  patterns: [get_or_404_owned (403-vs-404 ownership check, D-08), user_id keyword-only list_paginated param, TYPE_CHECKING forward-ref for cross-package model import cycle avoidance, Alembic TRUNCATE-then-add-NOT-NULL migration for empty table]
key_files:
  created:
    - alembic/versions/0003_add_user_id_to_notes.py
    - tests/test_notes_isolation.py
    - tests/test_notes_service_isolation.py
  modified:
    - app/notes/models.py (user_id FK + owner relationship)
    - app/notes/schemas.py (user_id in NoteRead)
    - app/notes/repository.py (create + list_paginated scoped)
    - app/notes/service.py (get_or_404_owned + current_user threading)
    - app/notes/router.py (all 5 handlers protected with get_current_user)
    - app/auth/models.py (User.notes relationship added)
    - tests/conftest.py (user_a_client + user_b_client fixtures)
    - tests/test_notes_crud.py (client → auth_client swap)
    - tests/test_notes_list.py (client → auth_client swap)
decisions:
  - "D-07: user_id NOT NULL indexed FK on notes (migration 0003)"
  - "D-08: cross-user 403 (not 404-hiding); missing note 404 — get_or_404_owned"
  - "D-09: GET /notes/ scoped WHERE Note.user_id == current_user.id"
  - "D-10: NoteCreate has no user_id; server assigns user_id=current_user.id"
  - "D-11: TRUNCATE TABLE notes before adding NOT NULL FK — dev data reset, no backfill"
  - "Migration deviation: add column as NOT NULL directly (not nullable then alter) to avoid MySQL ER_FK_COLUMN_CANNOT_CHANGE_CHILD when FK exists on column"
metrics:
  duration: "~29 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 9
requirements-completed: [AUTH-04]
---

# Phase 03 Plan 03: Per-User Data Isolation Summary

**One-liner:** Notes domain fully isolated per user — `notes.user_id` NOT NULL FK via migration 0003, `get_or_404_owned` ownership gate (403/404), all 5 note endpoints protected with `get_current_user`, and cross-user isolation proven by 12 new integration tests against real MySQL (66 total passing).

## What Was Built

### Task 1: notes.user_id FK — model + migration

**app/notes/models.py** — Added `user_id: Mapped[int]` column (`INTEGER(unsigned=True)`, FK → `users.id ON DELETE CASCADE`, `nullable=False`, `indexed=True`) and `owner: Mapped["User"]` relationship with `back_populates="notes"`. Used `TYPE_CHECKING` import to avoid circular import between `app.notes.models` and `app.auth.models`.

**app/auth/models.py** — Added `notes: Mapped[list[Note]]` relationship with `back_populates="owner"` and `cascade="all, delete-orphan"` (deferred from plan 01; now safe because FK migration runs). Same `TYPE_CHECKING` pattern for `Note`.

**app/notes/schemas.py** — Added `user_id: int` to `NoteRead` so API consumers see the owner. `NoteCreate` and `NoteUpdate` intentionally have NO `user_id` field (D-10 — body-supplied user_id is silently ignored because it's not in the schema).

**alembic/versions/0003_add_user_id_to_notes.py** — Migration sequence:
1. `TRUNCATE TABLE notes` (D-11 — dev data reset, no backfill needed)
2. `op.add_column("notes", ... nullable=False)` — directly NOT NULL (safe after TRUNCATE)
3. `op.create_foreign_key("fk_notes_user_id", ..., ondelete="CASCADE")`
4. `op.create_index("ix_notes_user_id", "notes", ["user_id"])`

`down_revision = "a1b2c3d4e5f6"` (chains from `0002_create_users_and_refresh_tokens` — users table must exist before FK, Pitfall 2).

### Task 2: Repository + service scoped to owner (TDD — RED then GREEN)

**app/notes/repository.py** changes:
- `create(data, user_id)`: passes `user_id` into `Note(...)` constructor (D-10)
- `list_paginated(..., *, user_id)`: adds `query = query.where(Note.user_id == user_id)` BEFORE the optional content filter, so count subquery and page query are both owner-scoped (D-09). `user_id` is keyword-only to prevent accidental positional misuse.
- `get_by_id`: UNCHANGED — ownership decision lives in the service (D-08)

**app/notes/service.py** changes:
- `create(data, user_id)`: threads `user_id` to repository
- `get_or_404_owned(note_id, current_user)`: fetch → 404 if None → 403 if `note.user_id != current_user.id` → return note (RESEARCH.md Pattern 4)
- `list_notes(..., *, user_id)`: threads `user_id` to repository (keyword-only)
- `update(note_id, data, current_user)`: uses `get_or_404_owned` before mutating
- `delete(note_id, current_user)`: uses `get_or_404_owned` before deletion
- `get_or_404`: kept for internal use

### Task 3: Router protected + isolation tests (TDD — RED then GREEN)

**app/notes/router.py** — All 5 handlers gain `current_user: User = Depends(get_current_user)`:
- `list_notes`: passes `user_id=current_user.id` to service
- `create_note`: passes `user_id=current_user.id` to service
- `get_note`: calls `get_or_404_owned(note_id, current_user)`
- `update_note`: calls `service.update(note_id, data, current_user)`
- `delete_note`: calls `service.delete(note_id, current_user)`

**tests/conftest.py** — Added `user_a_client` and `user_b_client` fixtures (function-scoped): each registers a distinct user (`a@example.com` / `b@example.com`), logs in, and returns a separate `AsyncClient` with the Bearer token pre-set, sharing the same transactional `session` for rollback isolation.

**tests/test_notes_isolation.py** (new) — 8 integration tests proving AUTH-04:
- `test_create/get/list_notes_requires_auth`: 401 without token
- `test_cross_user_get/put/delete_returns_403`: 403 for cross-user access
- `test_missing_note_returns_404`: 404 for nonexistent note (authenticated)
- `test_list_isolation`: A's list never contains B's notes; B's list never contains A's
- `test_create_assigns_owner`: response `user_id` equals authenticated user's id; body `user_id` ignored

**tests/test_notes_service_isolation.py** (new) — 6 unit-level integration tests for repository/service layer (TDD Task 2 RED/GREEN cycle).

**tests/test_notes_crud.py + tests/test_notes_list.py** — All `client` fixture arguments swapped to `auth_client` (Pitfall 5). Test bodies unchanged.

## Task Commits

1. **feat(03-03): add notes.user_id FK — model, schema, migration** — `b408616`
2. **test(03-03): add failing unit tests for repository/service user_id scoping (RED)** — `ae91824`
3. **feat(03-03): scope notes repository + service to owner (GREEN)** — `b53ecde`
4. **test(03-03): add failing isolation tests + user_a/user_b fixtures (RED)** — `0253e18`
5. **feat(03-03): protect notes router with get_current_user + isolation tests green (GREEN)** — `d354adc`

## TDD Gate Compliance

Task 2 and Task 3 both followed RED → GREEN:
- Task 2 RED: `ae91824` (test) — confirmed `TypeError: NoteRepository.create() got an unexpected keyword argument 'user_id'`
- Task 2 GREEN: `b53ecde` (feat) — 6 unit tests pass
- Task 3 RED: `0253e18` (test) — confirmed `TypeError: NoteService.create() missing 1 required positional argument: 'user_id'`
- Task 3 GREEN: `d354adc` (feat) — 66 total tests pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MySQL rejects ALTER TABLE MODIFY on column with existing FK constraint**
- **Found during:** Task 1 — first RED test run; `sqlalchemy.exc.OperationalError: (1832, "Cannot change column 'user_id': used in a foreign key constraint 'fk_notes_user_id'")`
- **Issue:** The RESEARCH.md Pattern 6 migration sequence called for: add nullable column → create FK → alter to NOT NULL. MySQL raises `ER_FK_COLUMN_CANNOT_CHANGE_CHILD` when trying to `ALTER TABLE MODIFY COLUMN` a column that already has an FK constraint on it.
- **Fix:** Added the column as `nullable=False` directly in `op.add_column`. This is safe because `TRUNCATE TABLE notes` runs first (table is empty), so the NOT NULL constraint is immediately satisfiable without any existing rows to violate it. The separate `alter_column` step was removed.
- **Files modified:** `alembic/versions/0003_add_user_id_to_notes.py`
- **Commit:** `ae91824` (included in RED commit since it was discovered during first test run)

**2. [Rule 1 - Lint] ruff I001 + F401 in test files**
- **Found during:** Task 3 — `ruff check` after writing isolation tests
- **Issue:** Import ordering (I001) in `tests/test_notes_isolation.py` and `tests/test_notes_service_isolation.py`; unused imports `httpx`, `Note`, `NoteUpdate` in `test_notes_service_isolation.py` (F401)
- **Fix:** `ruff check --fix` applied automatically
- **Commit:** `d354adc` (included in GREEN commit)

## Known Stubs

None. All endpoints are fully wired with real user isolation. The `user_id` field in `NoteRead` is populated from the actual DB column. No placeholder values or hardcoded data.

## Threat Surface

All new surface is within the plan's `<threat_model>`:

| Mitigation | Status |
|------------|--------|
| T-03-15: IDOR — user A reads user B's note | Mitigated: `get_or_404_owned` → 403; `test_cross_user_get_returns_403` passes |
| T-03-16: List endpoint leaks cross-user notes | Mitigated: `WHERE Note.user_id == user_id` in both count and page; `test_list_isolation` passes |
| T-03-17: Client forges note ownership via body user_id | Mitigated: `NoteCreate` has no `user_id` field; `test_create_assigns_owner` proves body `user_id` is ignored |
| T-03-18: Unauthenticated access to note endpoints | Mitigated: `Depends(get_current_user)` on all 5 handlers → 401; `test_*_requires_auth` passes |
| T-03-19: Cross-user write/delete | Mitigated: `update/delete` use `get_or_404_owned` → 403; isolation tests pass |
| T-03-20: NOT NULL FK migration failure | Mitigated: TRUNCATE + add NOT NULL directly; down_revision chains to users migration |
| T-03-21: 404-hiding vs 403 ambiguity | Accepted: D-08 deliberately returns 403 for existing-but-unowned notes |

## Self-Check: PASSED

Created files exist on disk:
- `alembic/versions/0003_add_user_id_to_notes.py` — FOUND
- `tests/test_notes_isolation.py` — FOUND
- `tests/test_notes_service_isolation.py` — FOUND

All 5 task commits found in git history:
- `b408616` — feat(03-03): add notes.user_id FK — model, schema, migration
- `ae91824` — test(03-03): add failing unit tests for repository/service user_id scoping (RED)
- `b53ecde` — feat(03-03): scope notes repository + service to owner (GREEN)
- `0253e18` — test(03-03): add failing isolation tests + user_a/user_b fixtures (RED)
- `d354adc` — feat(03-03): protect notes router with get_current_user + isolation tests green (GREEN)

Final verification:
- `uv run pytest tests/ -x` → **66 passed**
- `uv run ruff check app/ tests/` → **All checks passed**
- `uv run mypy app/` → **Success: no issues found in 22 source files**

---
*Phase: 03-auth-per-user-data-isolation*
*Plan: 03*
*Completed: 2026-06-25*
