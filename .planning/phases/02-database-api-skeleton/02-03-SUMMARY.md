---
phase: "02"
plan: "03"
name: "list-pagination-sort-filter-hardening"
subsystem: "notes, api, testing"
tags: ["pagination", "sort-whitelist", "filter", "ilike", "tdd", "mysql", "fastapi"]
dependency_graph:
  requires: ["02-02"]
  provides: ["sort-whitelist-422", "ilike-filter", "accurate-filtered-count", "list-test-matrix"]
  affects: ["03-auth", "04-tags-search"]
tech_stack:
  added: []
  patterns:
    - "Sort whitelist dict {created_at: Note.created_at, updated_at: Note.updated_at} — token mapped to ORM column object (T-02-11)"
    - "ValueError in repository → HTTPException 422 in service (T-02-14)"
    - "ilike(f'%{filter}%') parameter-bound filter (T-02-12)"
    - "select(func.count()).select_from(query.subquery()) counted AFTER filter, BEFORE offset/limit"
    - "Monotone-direction created_at ordering test (handles MySQL DATETIME 1-second granularity)"
key_files:
  created:
    - "tests/test_notes_list.py"
  modified:
    - "app/notes/repository.py"
    - "app/notes/service.py"
decisions:
  - "Sort whitelist implemented as a module-level dict mapping string tokens to ORM InstrumentedAttribute objects — no silent fallback; unknown token raises ValueError immediately"
  - "Service layer translates ValueError to HTTPException 422 (not 500) — keeps HTTP concerns out of repository (D-12 pattern)"
  - "Sort ordering tests use monotone direction check on created_at values (not ID positions) to handle MySQL DATETIME 1-second granularity ties"
metrics:
  duration_minutes: 9
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  tests_added: 16
  completed_date: "2026-06-24"
---

# Phase 02 Plan 03: List Pagination, Sort, Filter Hardening Summary

## One-Liner

Hardened `list_paginated` with a sort whitelist (ValueError→422 on unknown token), ilike filter (parameter-bound), accurate filtered count, and 16-test list-contract matrix against real MySQL.

## What Was Built

### Repository (`app/notes/repository.py`)

- Added `_SORT_WHITELIST: dict[str, InstrumentedAttribute]` at module level mapping `"created_at"` and `"updated_at"` to their ORM column objects (D-07, T-02-11).
- `list_paginated` now strips one leading `-` for direction, maps remaining token through the whitelist; raises `ValueError(f"invalid sort field: {token!r}")` if not found — no silent fallback.
- Filter applies `Note.content.ilike(f"%{filter}%")` when truthy — user value is a SQLAlchemy bound parameter, not concatenated into SQL text (T-02-12).
- `total` computed via `select(func.count()).select_from(query.subquery())` AFTER filter but BEFORE offset/limit — count reflects matched rows, not page length.
- Pagination applied last: `.offset((page-1)*size).limit(size)`.

### Service (`app/notes/service.py`)

- `list_notes` now wraps the repository call in a `try/except ValueError` block.
- A `ValueError` from an invalid sort token is translated to `HTTPException(status_code=422, detail=str(exc))` — returns a clean 422 with the error message, not a 500 with a stack trace (T-02-14).
- `pages = (total + size - 1) // size if total > 0 else 0` preserved — yields 0 when total==0.

### Test Suite (`tests/test_notes_list.py`)

16 tests covering the full list contract (authoritative from plan Task 1):

- **Envelope**: `GET /notes/` returns 200 with keys `{items, total, page, size, pages}`; defaults `page=1`, `size=20`.
- **Pagination math**: 5 seeded notes, `?page=2&size=2` → `len(items)==2`, `total==5`, `page==2`, `size==2`, `pages==3`.
- **Oversized/zero params**: `?size=101` → 422; `?size=0` → 422; `?page=0` → 422.
- **Sort direction**: `?sort=created_at` → non-decreasing `created_at` values; default `-created_at` → non-increasing `created_at` values; both together verify opposite monotone directions.
- **Valid sort field**: `?sort=updated_at` → 200.
- **Bad sort**: `?sort=content` → 422; `?sort=evil` → 422.
- **Case-insensitive filter**: `?filter=dock` matches notes containing "docker"; `?filter=DOCK` also matches.
- **Filtered total**: `total` reflects count of filtered matches, not full collection size.
- **Empty result**: `?filter=zzz_no_match_xqz` → `items==[]`, `total==0`, `pages==0`.

No DB mocks — all 16 tests run against real MySQL via the `client` fixture (testcontainers + transaction rollback).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Sort ordering tests fragile against MySQL DATETIME 1-second granularity**
- **Found during:** Task 2 test run (first run of `test_sort_default_desc_newest_first`)
- **Issue:** Original tests tracked note IDs by position (e.g., `returned_ids.index(ids[-1]) < returned_ids.index(ids[0])`). Within the same transaction, all POSTed notes may receive the same `created_at` value (MySQL DATETIME precision is 1 second), making the secondary ordering non-deterministic.
- **Fix:** Changed sort ordering tests (`test_sort_created_at_ascending_oldest_first`, `test_sort_default_desc_newest_first`, `test_sort_created_at_opposite_order_from_default`) to verify the `created_at` field sequence is monotonically non-decreasing (asc) or non-increasing (desc) — correctly handles timestamp ties.
- **Files modified:** `tests/test_notes_list.py`
- **Commit:** `1c20f72`

## Threat Surface

All threats from the plan's threat model were mitigated:

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-11 (SQL injection via ORDER BY) | Sort token mapped through `_SORT_WHITELIST` dict to ORM columns; unknown tokens raise ValueError→422; raw string never interpolated into SQL | Mitigated |
| T-02-12 (SQL injection via LIKE filter) | `Note.content.ilike(f"%{filter}%")` binds user value as parameter; f-string only shapes wildcards around bound value | Mitigated |
| T-02-13 (DoS via large page sizes) | `Query(ge=1, le=100)` enforces 422 on violation — unchanged from Plan 02 | Mitigated |
| T-02-14 (Info disclosure on bad sort) | ValueError from repository → clean 422 in service; no 500 stack trace exposed | Mitigated |
| T-02-15 (Cross-user list) | Accepted (no auth this phase — Phase 3) | Accepted |

## Known Stubs

None — all list contract features are fully wired and tested.

## Self-Check: PASSED

- tests/test_notes_list.py — FOUND
- app/notes/repository.py — FOUND (sort whitelist + ValueError)
- app/notes/service.py — FOUND (ValueError → HTTPException 422)
- Commit 311205d (test RED state): FOUND
- Commit 1c20f72 (feat harden + fix sort tests GREEN): FOUND
- `uv run pytest tests/ --asyncio-mode=auto -q` — 27 passed (11 health+CRUD + 16 list)
- `uv run ruff check app/ tests/` — all checks passed
- `grep -rn "create_all" app/ alembic/` — no matches
