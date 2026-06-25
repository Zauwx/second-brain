---
phase: 03-auth-per-user-data-isolation
plan: "02"
subsystem: auth
tags: [jwt, auth, refresh-token, rotation, logout, httpbearer, get_current_user, pyjwt]
dependency_graph:
  requires: [03-01 (AuthService/AuthRepository, User+RefreshToken models, refresh_tokens table, token pair, auth fixtures)]
  provides: [get_current_user HTTPBearer dependency, POST /auth/refresh (rotation), POST /auth/logout (204), 401 token semantics]
  affects: [app/notes/* (Plan 03 threads get_current_user through every note route), app/core/dependencies.py]
tech_stack:
  added: []
  patterns: [HTTPBearer(auto_error=False)→explicit-None→401, refresh-token rotation (revoke old jti + issue new pair), 204-on-logout, stateless JWT + DB jti revocation state]
key_files:
  created: []
  modified:
    - app/core/dependencies.py (added get_current_user + bearer_scheme; get_db/get_note_service unchanged)
    - app/auth/service.py (added AuthService.rotate_refresh_token + AuthService.logout)
    - app/auth/router.py (added POST /refresh (200) and POST /logout (204))
    - tests/test_auth.py (un-skipped the 2 Plan-02 placeholders; added refresh/logout/401 + dependency-unit coverage)
decisions:
  - "D-03: Concurrent refresh tokens are independent — rotating one jti leaves a user's other refresh tokens valid (no family/cascade revocation)"
  - "D-04: Rotation on refresh — decode refresh JWT, revoke old jti, issue a new access+refresh pair with a fresh jti persisted in refresh_tokens"
  - "D-05: Logout flips the jti's revoked flag → 204; a later refresh with that token returns 401"
  - "D-06: Minimal reuse handling — revoked/absent jti → 401, no reuse-detection cascade"
  - "Pitfall 3: HTTPBearer(auto_error=False) + explicit None check guarantees 401 (not FastAPI's default 403) on a missing Authorization header"
  - "Pitfall 4 / T-03-13: access + refresh payloads carry only sub + exp (+ jti on refresh); user attributes are fetched from the DB on every request"
requirements-completed: [AUTH-03]
metrics:
  duration: "~partial agent run (session-limit interrupted) + orchestrator finalization"
  completed: "2026-06-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 4
---

# Phase 03 Plan 02: Token Lifecycle — Refresh Rotation, Logout, get_current_user Summary

**One-liner:** Completed the JWT token lifecycle — `get_current_user` HTTPBearer gate (401 not 403 on missing/expired/invalid/deleted-user tokens), `POST /auth/refresh` with old-jti revocation + new pair issuance, and `POST /auth/logout` (204) — all proven against real MySQL via testcontainers.

## What Was Built

### app/core/dependencies.py — `get_current_user`
The bearer gate every protected route will use (Plan 03 threads it through the notes domain). `bearer_scheme = HTTPBearer(auto_error=False)` so a missing/malformed header yields our explicit 401 rather than FastAPI's default 403 (Pitfall 3, T-03-08). `get_current_user` decodes the access token (HS256, `settings.jwt_secret_key`), maps `ExpiredSignatureError`/`InvalidTokenError` → 401, extracts `sub`, then does a DB lookup via `AuthRepository(db).get_user_by_id(int(sub))` — a missing user (deleted after token issuance) returns 401 (T-03-12). Existing `get_db` and `get_note_service` were left unchanged.

### app/auth/service.py — `rotate_refresh_token` + `logout`
- **`rotate_refresh_token(refresh_token_str) -> TokenResponse`** (D-04): decodes the refresh JWT (→401 on expired/invalid), extracts `jti`+`sub`, looks up the row via `get_refresh_token_by_jti`; if missing or already revoked → 401 ("Refresh token revoked or not found"). Otherwise revokes the old jti, issues a fresh access+refresh pair, persists the new jti, and returns the new `TokenResponse`. Only the presented token's row is touched (D-03).
- **`logout(refresh_token_str) -> None`** (D-05): decodes the token, looks up the jti, and revokes it if present and not already revoked; router maps the `None` return to 204. No cascade/family revocation (D-06).

### app/auth/router.py
- `POST /refresh` → 200, `response_model=TokenResponse`, body `RefreshRequest`.
- `POST /logout` → 204 (`HTTP_204_NO_CONTENT`), body `LogoutRequest`, `-> None` (mirrors the notes `delete_note` 204 pattern).

### tests/test_auth.py
The two Plan-01 placeholders (`test_refresh_rotation`, `test_logout_*`) were un-skipped and implemented, plus the full refresh/logout/401 matrix and direct unit tests of `get_current_user` (called with a fabricated `HTTPAuthorizationCredentials` and the test session). Full auth suite now **24 passing, 0 skipped**.

## Task Commits

Implemented via TDD (RED → GREEN), then a lint fix:

1. **RED — failing tests for get_current_user + refresh/logout** — `6e13ccc` (test)
2. **GREEN — get_current_user HTTPBearer dependency** — `b18d8f9` (feat)
3. **GREEN — refresh rotation + logout (service + router)** — `3c05678` (feat)
4. **Lint — ruff I001 import ordering in tests/test_auth.py** — `0e3cf7c` (style)

**Plan metadata:** this SUMMARY (`docs(03-02)`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] ruff I001 import ordering in tests/test_auth.py**
- **Found during:** Task 2 — `ruff check` after adding refresh/logout tests
- **Issue:** Import block ordering flagged (I001) after new imports were added for the lifecycle tests.
- **Fix:** `ruff check --fix` reordered imports.
- **Committed in:** `0e3cf7c`

**Total deviations:** 1 auto-fixed (lint). No scope creep.

## Issues Encountered

The executor agent hit a session/usage limit **after** committing all implementation (RED + both GREEN commits + the ruff fix) but **before** writing this SUMMARY. The working tree was clean and all work was committed. The orchestrator verified the merged result independently (see Self-Check) and authored this SUMMARY from the verified state rather than re-running the plan. No implementation work was redone or lost.

## Next Phase Readiness

`get_current_user` is the gate Plan 03 (per-user data isolation) threads through every note endpoint. The refresh/logout lifecycle and 401 semantics are complete. Ready for Plan 03 to add `notes.user_id` and scope all note reads/writes to the authenticated owner.

## Self-Check: PASSED

Verified on the merged phase branch (`gsd/phase-03-auth-per-user-data-isolation`):
- `uv run pytest tests/test_auth.py -q` → **24 passed**
- `uv run ruff check app/ tests/` → **All checks passed**
- `uv run mypy app/auth/ app/core/dependencies.py` → **Success: no issues found in 7 source files**
- `app/core/dependencies.py` contains `async def get_current_user` and `HTTPBearer(auto_error=False)`; `get_db`/`get_note_service` still present
- `app/auth/service.py` contains `rotate_refresh_token` and `logout`; `app/auth/router.py` defines `/refresh` (200) and `/logout` (204)
- All four task commits present in git history (`6e13ccc`, `b18d8f9`, `3c05678`, `0e3cf7c`)

---
*Phase: 03-auth-per-user-data-isolation*
*Completed: 2026-06-25*
