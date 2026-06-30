---
phase: 04-tags-collections-full-text-search
plan: 02
subsystem: notes/tags
tags: [tags, filter, AND-intersection, ORG-02, selectinload, mysql, fastapi, tdd]
dependency_graph:
  requires: [04-01]
  provides: ["GET /notes?tag=", "AND-intersection tag filter", "ORG-02"]
  affects: [app/notes/repository.py, app/notes/service.py, app/notes/router.py, tests/test_notes_tag_filter.py]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy subquery: tag-id scalar_subquery scoped to user_id
    - HAVING COUNT(DISTINCT tag_id) == N for strict AND-intersection
    - Function-level import of Tag to avoid module-level circular import
    - Repeatable Query param list[str] | None = Query(default=None) in FastAPI
key_files:
  created:
    - tests/test_notes_tag_filter.py
  modified:
    - app/notes/repository.py
    - app/notes/service.py
    - app/notes/router.py
decisions:
  - "Tag imported function-level in repository (not module-level) to avoid circular import with app.tags.models"
  - "note_tags Table imported at module level (same module as Note, no circular risk)"
  - "tag query param named 'tag' (singular) in router, threaded as 'tags' (plural) to service/repo — matches REST convention for repeatable params"
metrics:
  duration_minutes: 15
  completed_date: "2026-06-29"
  tasks_completed: 2
  files_touched: 4
---

# Phase 4 Plan 02: Tag Filter (AND-Intersection) Summary

**One-liner:** ORG-02 delivered — `GET /notes?tag=python&tag=docker` returns only notes carrying ALL listed tags via a user-scoped `HAVING COUNT(DISTINCT tag_id) == N` subquery, normalized input, selectinload, composed with existing pagination/sort/content-filter.

## What Was Built

Delivered ORG-02 tag filtering on the existing note list endpoint:

- **Repository** (`app/notes/repository.py`): Extended `list_paginated` with `tags: list[str] | None = None` parameter (before the keyword-only `*, user_id`). When truthy, builds two correlated subqueries:
  1. `tag_id_subq` — `SELECT Tag.id WHERE Tag.name IN (normalized_tags) AND Tag.user_id = user_id` (T-04-iso: cross-user tag match prevented)
  2. `matching_note_ids` — `SELECT note_id FROM note_tags WHERE tag_id IN (tag_id_subq) GROUP BY note_id HAVING COUNT(DISTINCT tag_id) = N` (strict AND, not OR)
  Then applies `WHERE Note.id IN (matching_note_ids)` on the outer query. `Tag` imported function-level to avoid circular imports. Existing `selectinload(Note.tags)`, count, sort, and pagination on the outer query are unchanged (Pitfall 5).

- **Service** (`app/notes/service.py`): Added `tags: list[str] | None = None` to `list_notes` signature, forwarded to `list_paginated`.

- **Router** (`app/notes/router.py`): Added `tag: list[str] | None = Query(default=None)` to `list_notes` endpoint, passed as `tags=tag` to service. FastAPI handles repeated `?tag=python&tag=docker` as a list automatically.

- **Tests** (`tests/test_notes_tag_filter.py`): 4 integration tests (TDD RED → GREEN):
  - `test_single_tag_filter` — `?tag=python` includes tagged note, excludes untagged
  - `test_multi_tag_and_filter` — `?tag=python&tag=docker` strict AND; python-only note excluded
  - `test_tag_filter_normalization` — `?tag=Python` matches stored `"python"` (Pitfall 6)
  - `test_filtered_items_include_tags` — filtered items carry populated tags array (selectinload)

## Verification

- `uv run pytest tests/test_notes_tag_filter.py tests/test_notes_list.py -q` — **20 passed, 0 failed**
- `uv run pytest tests/ -q` — **84 passed, 0 failed** (full suite)
- `uv run ruff check app/notes` — clean
- `uv run mypy app/notes` — clean (6 source files, no issues)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

- **T-04-iso:** `tag_id_subq` filters `Tag.user_id == user_id` AND outer query keeps `Note.user_id == user_id` — cross-user tag lookup impossible.
- **T-04-04:** All values parameterized via SQLAlchemy ORM `in_()`/`having()` — no `text()` or f-string SQL interpolation.
- **T-04-05:** Single GROUP BY/HAVING pass; pagination caps result size — no N+1 amplification.
- **T-04-SC:** No new packages installed.

## Known Stubs

None. All filtering is fully implemented against real MySQL data.

## Self-Check: PASSED

- `tests/test_notes_tag_filter.py` — FOUND
- `app/notes/repository.py` (tags param + subquery) — FOUND
- `app/notes/service.py` (tags threaded) — FOUND
- `app/notes/router.py` (tag Query param) — FOUND
- Commits 0734c35 (test), 92831f0 (feat) — in git log
- 84 tests passed, 0 failed
