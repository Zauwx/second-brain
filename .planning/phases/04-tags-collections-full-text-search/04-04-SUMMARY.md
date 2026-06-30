---
phase: 04-tags-collections-full-text-search
plan: 04
subsystem: search
tags: [search, fulltext, mysql, boolean-mode, SRCH-01, sanitization, user-isolation]
dependency_graph:
  requires: [04-01-tags-vertical-slice, 04-03-collections-vertical-slice]
  provides: ["GET /search/?q=", search_fulltext BOOLEAN MODE, sanitize_boolean_query]
  affects: [app/core/dependencies.py, app/main.py, tests/conftest.py]
tech_stack:
  added: []
  patterns:
    - "sqlalchemy.dialects.mysql.match().in_boolean_mode() — parameterized FULLTEXT BOOLEAN MODE"
    - "sanitize_boolean_query() — strip @/++/+- before AGAINST clause"
    - "ft_session fixture — committed session for FULLTEXT tests (InnoDB only sees committed data)"
    - NoteListResponse envelope reused verbatim for /search
key_files:
  created:
    - app/search/__init__.py
    - app/search/schemas.py
    - app/search/repository.py
    - app/search/service.py
    - app/search/router.py
    - tests/test_search.py
  modified:
    - docker-compose.yml
    - app/main.py
    - app/core/dependencies.py
    - tests/conftest.py
decisions:
  - "ft_session fixture uses engine-direct sessions (no outer rollback transaction) for FULLTEXT tests — InnoDB FULLTEXT indexes are updated on COMMIT, not on SAVEPOINT release; the standard rollback fixture produces zero FULLTEXT results even for freshly inserted rows"
  - "Cleanup in ft_session uses DELETE FROM users with CASCADE rather than TRUNCATE — avoids DDL implicit-commit ordering complexity and is sufficient for per-test isolation"
  - "search router inlines SearchService(SearchRepository(session)) — consistent with existing router pattern; get_search_service added to dependencies.py for completeness"
  - "mypy type: ignore[arg-type] on match() call — sqlalchemy.dialects.mysql.match stubs declare ColumnElement[Any] but InstrumentedAttribute[str | None] is correct at runtime"
metrics:
  duration_minutes: 20
  completed_date: "2026-06-29"
  tasks_completed: 2
  files_touched: 10
---

# Phase 4 Plan 04: Full-Text Search Vertical Slice Summary

**One-liner:** FULLTEXT BOOLEAN MODE search (SRCH-01) implemented as a vertical slice — user-scoped, parameterized MATCH AGAINST with `sanitize_boolean_query` stripping malformed operators, returning the canonical NoteListResponse envelope; 2-char tokens (AI, Go) searchable via innodb_ft_min_token_size=2.

## What Was Built

Delivered the Full-Text Search vertical slice:

- **docker-compose.yml** — added `command: --innodb-ft-min-token-size=2` to the mysql service so the production stack matches the test container configuration (D-11). Startup-only variable; cannot be set at runtime via SET GLOBAL.

- **Search package** (`app/search/`):
  - `__init__.py` — empty package marker.
  - `schemas.py` — re-exports `NoteListResponse` from `app.notes.schemas`; no new class needed (single canonical envelope, D-06).
  - `repository.py` — `SearchRepository.search_fulltext(q, user_id, page, size)` using `from sqlalchemy.dialects.mysql import match` → `match(Note.title, Note.content, against=q).in_boolean_mode()`. Parameterized binding (T-04-inj). User-scoped via `.where(Note.user_id == user_id)` (T-04-iso). Selectinload(Note.tags) on every result row (prevents MissingGreenlet in Pydantic serialization). Count-then-fetch pattern mirroring `NoteRepository.list_paginated`.
  - `service.py` — module-level `sanitize_boolean_query(q) -> str | None` strips `@` (reserved for unsupported @distance proximity), removes consecutive `+/-` sequences, removes trailing operators, collapses whitespace; returns None for empty result (T-04-08). `SearchService.search()` short-circuits to empty NoteListResponse when sanitized query is None — avoids a DB round-trip and guarantees 200 for pure-operator inputs.
  - `router.py` — `APIRouter(tags=["search"])`. `GET /` with `q: str = Query(..., min_length=1)`, `page`, `size`; `get_current_user` dependency (T-04-09); inlines `SearchService(SearchRepository(session))`.

- **Router registration** (`app/main.py`) — `app.include_router(search_router, prefix="/search")`.

- **Dependencies** (`app/core/dependencies.py`) — `get_search_service` provider added for completeness (router inlines directly but provider exists for injection use cases).

- **Test coverage** (`tests/test_search.py`, 11 tests):
  - `test_basic_search_returns_matching_notes` — POST note with "python", GET /search/?q=python, assert total >= 1 and content contains "python"
  - `test_search_returns_canonical_envelope` — verifies {items, total, page, size, pages} keys + default values
  - `test_two_char_token_search` — POST note with "AI", GET /search/?q=AI, assert total >= 1 (proves min_token_size=2)
  - `test_search_isolation` — user A's private note is invisible to user B's search (total == 0)
  - `test_boolean_operators_return_200` — `+python -docker` returns 200
  - `test_wildcard_operator_returns_200` — `python*` returns 200
  - `test_stray_at_operator_returns_200` — `@@test` sanitized → 200
  - `test_consecutive_plus_operators_returns_200` — `++word` sanitized → 200
  - `test_mixed_stray_operators_returns_200` — `@@++` sanitized → 200
  - `test_whitespace_only_query_returns_empty_envelope` — whitespace-only q → empty envelope
  - `test_search_requires_auth` — 401 without token

- **conftest.py extension** — `ft_session`, `ft_client`, `ft_auth_client` fixtures added for FULLTEXT-requiring tests (see Deviations).

## Verification

- `uv run pytest tests/test_search.py -q` — **11 passed, 0 failed**
- `uv run pytest tests/ -q` — **101 passed, 0 failed** (full suite, no regressions)
- `uv run ruff check app/search app/main.py app/core/dependencies.py tests/conftest.py tests/test_search.py` — clean
- `uv run mypy app/search app/core/dependencies.py app/main.py` — clean (7 source files, no issues)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy arg-type error on sqlalchemy.dialects.mysql.match()**

- **Found during:** Task 2 `uv run mypy app/search` verification
- **Issue:** `match(Note.title, Note.content, against=q)` — mypy inferred `InstrumentedAttribute[str | None]` is incompatible with `ColumnElement[Any]` expected by the SQLAlchemy dialect stubs. This is a known stubs invariance false positive; the call is correct at runtime.
- **Fix:** Added `# type: ignore[arg-type]` to the match line in `app/search/repository.py`.
- **Files modified:** `app/search/repository.py`
- **Commit:** d8492e0

**2. [Rule 2 - Missing Critical Functionality] InnoDB FULLTEXT only sees committed data — test fixture incompatibility**

- **Found during:** Task 2 test run (`test_basic_search_returns_matching_notes` and `test_two_char_token_search` failed with total == 0 despite notes being created)
- **Issue:** MySQL InnoDB FULLTEXT indexes are updated on `COMMIT`, not on `SAVEPOINT` release. The standard test `session` fixture opens an outer rollback transaction and never issues a real COMMIT to disk. `NoteRepository.create()` calls `session.commit()` which, when the session is bound to a connection with an open outer transaction, releases a SAVEPOINT (not a real commit). The FULLTEXT index therefore sees zero rows for freshly inserted notes.
- **Fix:** Added three fixtures to `tests/conftest.py`:
  - `ft_session` — creates a session directly from the test engine (no outer rollback transaction), so `session.commit()` in route handlers issues a real DB commit visible to FULLTEXT. Teardown executes `DELETE FROM users` (CASCADE removes notes/tags/collections/junction rows) + `session.commit()` to clean up committed data.
  - `ft_client` — AsyncClient backed by `ft_session`.
  - `ft_auth_client` — pre-authenticated `ft_client`.
  Changed `test_basic_search_returns_matching_notes` and `test_two_char_token_search` to use `ft_auth_client`.
- **Files modified:** `tests/conftest.py`, `tests/test_search.py`
- **Commit:** d8492e0

## Threat Model Compliance

All T-04-* mitigations implemented as planned:

- **T-04-inj:** `match(against=q)` binds `q` as a SQL parameter — no string interpolation, no injection risk. `sanitize_boolean_query` removes operator combinations that cause InnoDB syntax errors. Verified by `test_stray_at_operator_returns_200`, `test_consecutive_plus_operators_returns_200`, `test_mixed_stray_operators_returns_200`.
- **T-04-iso:** `.where(Note.user_id == user_id)` on every search query — verified by `test_search_isolation` (total == 0 when searching for another user's content).
- **T-04-08:** Sanitizer removes error-causing operator combos; whitespace-only q returns empty envelope without DB call; pagination caps result size.
- **T-04-09:** `get_current_user` JWT dependency (401) inherited from Phase 3, applied to `GET /search/`. Verified by `test_search_requires_auth`.
- **T-04-SC:** No new packages installed this plan.

## Known Stubs

None. The search endpoint queries real MySQL FULLTEXT data; no placeholder responses.

## Threat Flags

None. No new network surfaces beyond the planned `/search` prefix. All endpoints are behind `get_current_user`.

## Self-Check: PASSED

- `app/search/__init__.py` — FOUND
- `app/search/repository.py` — FOUND (contains `in_boolean_mode`)
- `app/search/service.py` — FOUND (contains `sanitize_boolean_query`)
- `app/search/router.py` — FOUND (exports `router`)
- `docker-compose.yml` — contains `innodb-ft-min-token-size=2`
- `tests/test_search.py` — FOUND (11 tests, 102 lines)
- Commits 2a51f65 (test+docker-compose), d8492e0 (implementation) — both in git log
- 101 tests passed, 0 failed
