---
phase: 03-auth-per-user-data-isolation
verified: 2026-06-25T12:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 03: Auth + Per-User Data Isolation — Verification Report

**Phase Goal:** Every note endpoint requires a valid JWT; each user sees only their own data; refresh token rotation is in place; cross-user access tests pass in CI.
**Verified:** 2026-06-25
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can register (POST /auth/register) → 201 + UserRead (no password fields) | VERIFIED | `app/auth/router.py:41-62` returns 201 + `UserRead`; `UserRead` schema has id/email/created_at only; `test_register_returns_201` asserts `"hashed_password" not in body` and passes |
| 2 | User can log in (POST /auth/login) → 200 + short-lived access token (15-min) + rotating refresh token stored in `refresh_tokens` table | VERIFIED | `app/auth/service.py:96-134` — `create_access_token` with 15-min expiry; `create_refresh_token` with jti UUID4; `repo.create_refresh_token` persists to DB. `test_login_returns_tokens` + `test_access_token_decodes_with_sub` pass |
| 3 | POST /auth/refresh with valid refresh token → new access_token + new refresh_token; old refresh token invalidated | VERIFIED | `AuthService.rotate_refresh_token` (`service.py:136-206`) decodes the refresh JWT, revokes old jti via `repo.revoke_refresh_token`, issues a new pair, persists new jti. `test_refresh_rotation`, `test_old_refresh_token_revoked_after_rotation`, `test_new_refresh_token_works_after_rotation` all pass |
| 4 | User A's JWT never returns user B's notes — GET/PUT/DELETE cross-user → 403/404; GET /notes/ list isolation | VERIFIED | `get_or_404_owned` in `notes/service.py:58-81` checks `note.user_id != current_user.id` → 403; `list_paginated` scoped with `WHERE Note.user_id == user_id` (`notes/repository.py:106`). Tests `test_cross_user_get/put/delete_returns_403`, `test_list_isolation`, `test_missing_note_returns_404` pass |
| 5 | Any protected endpoint with no token or expired token → 401 | VERIFIED | `HTTPBearer(auto_error=False)` + explicit None check (`dependencies.py:41,80-81`); `ExpiredSignatureError`/`InvalidTokenError` → 401 (`dependencies.py:89-91`). Tests `test_no_token_returns_401`, `test_invalid_token_returns_401`, `test_expired_token_returns_401`, `test_create_note_requires_auth`, `test_get_note_requires_auth`, `test_list_notes_requires_auth` all pass |

**Score:** 5/5 truths verified

---

### Test Suite Result

`uv run pytest tests/ -q` — **66 passed in 14.23s** (confirmed live run, no skipped or failed tests)

Test breakdown covering phase goals:
- `tests/test_auth.py` — AUTH-01, AUTH-02, AUTH-03 (register, login, refresh rotation, logout, get_current_user unit tests)
- `tests/test_notes_isolation.py` — AUTH-04 (cross-user 403, list isolation, 401 no-auth, owner assignment)
- `tests/test_notes_service_isolation.py` — repository/service scoping unit tests
- `tests/test_notes_crud.py` + `tests/test_notes_list.py` — upgraded to `auth_client` fixture; all pass under authenticated context

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/auth/models.py` | User + RefreshToken ORM models | VERIFIED | `class User` and `class RefreshToken` present; InnoDB/utf8mb4 `__table_args__`; INTEGER(unsigned=True) PKs; UNIQUE email; FK user_id on RefreshToken |
| `app/auth/schemas.py` | UserCreate (with validator), UserRead (no password), TokenResponse | VERIFIED | `@field_validator("password")` enforces D-13; `UserRead` has id/email/created_at only; `TokenResponse` has access_token/refresh_token/token_type |
| `app/auth/repository.py` | create_user, get_user_by_id, get_user_by_email, create/get/revoke_refresh_token | VERIFIED | All 6 methods present and substantive; real DB queries |
| `app/auth/service.py` | AuthService with register, login, rotate_refresh_token, logout | VERIFIED | All methods present; `PasswordHash.recommended()` at module level; `create_access_token` and `create_refresh_token` helpers present |
| `app/auth/router.py` | POST /register (201), POST /login (200), POST /refresh (200), POST /logout (204) | VERIFIED | All 4 routes defined; correct status codes; response_models wired |
| `app/core/dependencies.py` | `get_current_user` with HTTPBearer(auto_error=False) | VERIFIED | `bearer_scheme = HTTPBearer(auto_error=False)` at line 41; `async def get_current_user` at line 57; existing `get_db`/`get_note_service` unchanged |
| `app/notes/repository.py` | `create(data, user_id)` + `list_paginated(..., *, user_id)` scoped | VERIFIED | `Note.user_id == user_id` filter applied before optional content filter; `user_id` keyword-only param |
| `app/notes/service.py` | `get_or_404_owned` (403 vs 404); update/delete use owned variant | VERIFIED | `get_or_404_owned` at line 58; `update` and `delete` both call `get_or_404_owned` |
| `app/notes/router.py` | All 5 handlers have `Depends(get_current_user)` | VERIFIED | Grep confirms exactly 5 occurrences of `Depends(get_current_user)` in router |
| `alembic/versions/0002_create_users_and_refresh_tokens.py` | users + refresh_tokens migration; down_revision chains from notes | VERIFIED | `revision="a1b2c3d4e5f6"`, `down_revision="d51191e92276"`; creates both tables with InnoDB/utf8mb4 |
| `alembic/versions/0003_add_user_id_to_notes.py` | notes.user_id FK migration; TRUNCATE + NOT NULL | VERIFIED | `op.execute("TRUNCATE TABLE notes")` present; `down_revision="a1b2c3d4e5f6"`; FK + index created |
| `tests/test_auth.py` | register/login/refresh/logout/get_current_user integration tests | VERIFIED | 24+ test functions; no skipped tests (Plan-01 placeholders were un-skipped in Plan 02) |
| `tests/test_notes_isolation.py` | Cross-user 403/404 + list isolation + no-auth 401 tests | VERIFIED | 8 tests covering all isolation cases; `user_a_client`/`user_b_client` fixtures used |
| `tests/test_notes_service_isolation.py` | Repository/service unit tests for ownership | VERIFIED | 6 tests; `_create_user` helper inserts real DB rows |
| `tests/conftest.py` | `registered_user`, `auth_client`, `user_a_client`, `user_b_client` fixtures | VERIFIED | All 4 fixtures present; `user_a_client`/`user_b_client` create independent `AsyncClient` instances with separate auth tokens |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/main.py` | `app/auth/router.py` | `include_router(auth_router, prefix="/auth")` | WIRED | `main.py:55` confirms |
| `app/main.py` | `app/notes/router.py` | `include_router(notes_router, prefix="/notes")` | WIRED | `main.py:56` confirms |
| `app/auth/router.py` | `app/auth/service.py` | `AuthService(AuthRepository(session))` via `_make_service` | WIRED | `router.py:36-38` |
| `app/notes/router.py` | `app/core/dependencies.py` | `current_user: User = Depends(get_current_user)` on all 5 handlers | WIRED | 5 occurrences confirmed by grep |
| `app/notes/repository.py` | `notes.user_id` | `query.where(Note.user_id == user_id)` in `list_paginated` | WIRED | `repository.py:106` |
| `app/core/dependencies.py` | `app/auth/repository.py` | `AuthRepository(db).get_user_by_id(int(user_id_str))` in `get_current_user` | WIRED | `dependencies.py:99` |
| `alembic/env.py` | `app/auth/models.py` | `from app.auth.models import User, RefreshToken` before `target_metadata` | WIRED | `env.py:40-43` |
| `alembic/versions/0003` | `alembic/versions/0002` | `down_revision = "a1b2c3d4e5f6"` | WIRED | Migration chain confirmed; users table exists before FK |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/notes/router.py` — `list_notes` | `current_user.id` → `user_id` | `get_current_user` → DB lookup by sub → real `User` row | Yes — DB query `select(User).where(User.id == user_id_str)` | FLOWING |
| `app/notes/router.py` — `create_note` | `current_user.id` | JWT sub → DB user | Yes | FLOWING |
| `app/notes/repository.py` — `list_paginated` | `items, total` | `select(Note).where(Note.user_id == user_id)` real DB query | Yes | FLOWING |
| `app/auth/service.py` — `login` | `access_token`, `refresh_token` | `create_access_token` + `create_refresh_token` with real `user.id` from DB | Yes | FLOWING |
| `app/auth/service.py` — `rotate_refresh_token` | new token pair | `jwt.decode` → `repo.get_refresh_token_by_jti` → DB lookup → real revocation + new jti | Yes | FLOWING |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AUTH-01 | 03-01 | User can sign up with email and password | SATISFIED | POST /auth/register → 201; duplicate → 409; bad email → 422; weak password → 422. 7 tests in test_auth.py cover all cases |
| AUTH-02 | 03-01 | User can log in and receive a JWT access token | SATISFIED | POST /auth/login → 200 + access_token + refresh_token + token_type=bearer; wrong password/email → 401. Token payload verified (sub=user_id, exp present) |
| AUTH-03 | 03-02 | User stays authenticated across requests with token refresh | SATISFIED | POST /auth/refresh rotates token (old jti revoked, new pair issued); POST /auth/logout → 204; refresh after logout → 401; concurrent tokens independent (D-03) |
| AUTH-04 | 03-03 | User can only access their own data | SATISFIED | All 5 note endpoints require bearer token; cross-user GET/PUT/DELETE → 403; list scoped to owner; notes.user_id FK NOT NULL; user_id assigned server-side |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/core/config.py` | 25 | `jwt_secret_key` has a hardcoded insecure default | WARNING (advisory, tracked in CR-01 of 03-REVIEW.md) | No impact on phase goal in dev/test; tokens are consistent within a run. Production hardening deferred per code review tracking. |
| `app/core/dependencies.py` | 99 | `int(user_id_str)` unguarded — non-numeric sub causes 500 | WARNING (advisory, tracked in CR-02 of 03-REVIEW.md) | Adversarial edge case only; all token issuance uses `str(user_id: int)`. All 66 tests pass. Phase success criteria do not require this guard. |
| `app/notes/service.py` | 44-56 | `get_or_404` (unscoped) still present — dead code footgun | WARNING (advisory, tracked in WR-03 of 03-REVIEW.md) | Not wired to any route; all endpoints use `get_or_404_owned`. No current leakage. |

No `TBD`, `FIXME`, or `XXX` markers found in `app/` or `tests/`. No placeholder return stubs. No hardcoded empty data arrays in production code.

---

### Advisory Items from Code Review (03-REVIEW.md)

The code review flagged 2 Critical and 7 Warning findings. Per verification scope, these are assessed only for whether they block the phase goal:

**CR-01 (hardcoded JWT secret default):** Does NOT block the phase goal. In development and test runs, `settings.jwt_secret_key` is used consistently for both issuance and verification — tokens work correctly. All 66 tests pass using this default. This is a production deployment hardening gap, not a functional correctness failure for this phase. Remediation tracked in 03-REVIEW.md.

**CR-02 (non-numeric `sub` → 500):** Does NOT block the phase goal. The success criterion is "no token or expired token → 401." A crafted token with a valid signature but non-integer `sub` is an adversarial input not covered by the success criteria. The only token issuance path (`create_access_token`) always uses `str(user_id: int)`. Remediation tracked in 03-REVIEW.md.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite (66 tests) | `uv run pytest tests/ -q` | 66 passed in 14.23s | PASS |
| `get_current_user` returns 401 on None credentials | `test_no_token_returns_401` in test suite | Confirmed passing | PASS |
| Cross-user 403 isolation | `test_cross_user_get_returns_403` in test suite | Confirmed passing | PASS |
| Refresh rotation revokes old jti | `test_old_refresh_token_revoked_after_rotation` in test suite | Confirmed passing | PASS |

---

### Human Verification Required

None. All success criteria are verified programmatically through the automated test suite against a real MySQL container (testcontainers). No UI, visual behavior, real-time behavior, or external service verification is required for this phase.

---

### Gaps Summary

No gaps. All 5 phase success criteria are verified by working code and passing tests.

---

_Verified: 2026-06-25T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
