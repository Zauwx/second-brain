---
phase: 03-auth-per-user-data-isolation
plan: "01"
subsystem: auth
tags: [jwt, auth, registration, login, pwdlib, argon2, pyjwt, alembic, migration]
dependency_graph:
  requires: [02-03 (notes CRUD + testcontainers harness)]
  provides: [users table, refresh_tokens table, POST /auth/register, POST /auth/login, auth token pair, registered_user fixture, auth_client fixture]
  affects: [alembic/env.py, app/main.py, tests/conftest.py]
tech_stack:
  added: [pyjwt==2.13.0, pwdlib[argon2]==0.3.0, email-validator==2.3.0 (via pydantic[email])]
  patterns: [PasswordHash.recommended() Argon2id, PyJWT HS256 encode/decode, IntegrityError→HTTP409, HTTPBearer auto_error=False deferred to Plan 02]
key_files:
  created:
    - app/auth/__init__.py
    - app/auth/models.py
    - app/auth/schemas.py
    - app/auth/repository.py
    - app/auth/service.py
    - app/auth/router.py
    - alembic/versions/0002_create_users_and_refresh_tokens.py
    - tests/test_auth.py
  modified:
    - pyproject.toml (added pyjwt, pwdlib[argon2], pydantic[email])
    - uv.lock
    - app/core/config.py (added jwt_secret_key, jwt_algorithm, access_token_expire_minutes, refresh_token_expire_days)
    - app/main.py (include_router auth_router prefix=/auth)
    - alembic/env.py (import User, RefreshToken before target_metadata)
    - tests/conftest.py (registered_user, auth_client fixtures)
    - app/notes/repository.py (pre-existing mypy fix: InstrumentedAttribute[datetime])
    - app/notes/service.py (pre-existing mypy fix: explicit NoteRead.model_validate in list comprehension)
decisions:
  - "D-01: Access token HS256, 15-min expiry; sub=str(user_id), exp only — no mutable claims"
  - "D-02: Refresh token is JWT with jti UUID4; jti persisted in refresh_tokens table for revocation"
  - "D-12: EmailStr validation via pydantic[email]; malformed email → 422"
  - "D-13: Password @field_validator: len>=8 + upper + lower + digit + symbol → 422"
  - "D-14: Duplicate email → 409 via IntegrityError catch in AuthService.register()"
  - "User.notes relationship deferred to Plan 02/03 when user_id FK is added to notes table"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-25"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 8
---

# Phase 03 Plan 01: Auth Foundation — Register and Login Summary

**One-liner:** JWT auth slice with Argon2id password hashing, HS256 token issuance (access 15 min + refresh 7 days with jti in DB), and /auth/register + /auth/login endpoints proven against real MySQL via testcontainers.

## What Was Built

Delivered the thinnest end-to-end authentication slice: a user can register an account and log in to receive a JWT access token plus a refresh token. This creates the `app/auth/` domain package, the `users` + `refresh_tokens` tables, and the register/login endpoints.

### app/auth/ Package Structure

Mirrors `app/notes/` exactly (domain-per-folder, PATTERNS.md):

- **models.py** — `User` (email UNIQUE, hashed_password, timestamps, InnoDB/utf8mb4) and `RefreshToken` (jti UUID36 UNIQUE indexed, user_id FK→users CASCADE, revoked/revoked_at, expires_at). `User.notes` relationship deferred until Plan 02/03 adds the user_id FK to the notes table.
- **schemas.py** — `UserCreate` with `@field_validator` enforcing D-13 (8+ chars, upper, lower, digit, symbol); `UserRead` (id, email, created_at — NO hashed_password, T-03-01); `LoginRequest`; `TokenResponse`; `RefreshRequest`/`LogoutRequest` scaffolded for Plan 02.
- **repository.py** — `AuthRepository`: create_user, get_user_by_id, get_user_by_email, create_refresh_token, get_refresh_token_by_jti, revoke_refresh_token.
- **service.py** — Module-level `PasswordHash.recommended()` (Argon2id). Stateless `create_access_token` and `create_refresh_token(user_id, secret, days) → (token, jti)` helpers. `AuthService.register()` catches `IntegrityError` → 409. `AuthService.login()` uses constant-time `password_hash.verify()` and returns `TokenResponse`.
- **router.py** — `POST /register` (201, response_model=UserRead), `POST /login` (200, response_model=TokenResponse).

### Migration: `0002_create_users_and_refresh_tokens.py`

- `down_revision = "d51191e92276"` (chains from notes migration)
- Creates `users` table: INTEGER UNSIGNED PK, email VARCHAR(255) UNIQUE, hashed_password VARCHAR(255), created_at, updated_at — InnoDB/utf8mb4
- Creates `refresh_tokens` table: INTEGER UNSIGNED PK, jti VARCHAR(36) UNIQUE indexed, user_id FK→users CASCADE indexed, expires_at, revoked BOOLEAN default 0, revoked_at nullable, created_at — InnoDB/utf8mb4

### Settings Extension

`app/core/config.py`: Added `jwt_secret_key`, `jwt_algorithm`, `access_token_expire_minutes`, `refresh_token_expire_days` — all read from `.env` (T-03-04, never hard-coded in images).

### Test Infrastructure

`tests/conftest.py`: Added `registered_user` and `auth_client` fixtures (function-scoped, reuse existing `client`). `tests/test_auth.py`: 11 passing tests covering AUTH-01 (register: 201, 409, 422 email/password), AUTH-02 (login: 200+tokens, 401 wrong-pw, 401 unknown-email), and D-01 token content (sub=str(user_id), exp present). Two tests skipped with explicit Plan 02 markers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Alembic revision ID exceeded VARCHAR(32)**
- **Found during:** Task 3 — first test run; migration failed with DataError "Data too long for column 'version_num' at row 1"
- **Issue:** Revision ID `0002_create_users_and_refresh_tokens` is 33 characters; Alembic's `alembic_version` table has `version_num VARCHAR(32)`.
- **Fix:** Changed revision to `a1b2c3d4e5f6` (12-character hash-style ID matching the notes migration format).
- **Files modified:** `alembic/versions/0002_create_users_and_refresh_tokens.py`
- **Commit:** 00403bd

**2. [Rule 1 - Bug] Premature User.notes relationship before FK exists**
- **Found during:** Task 3 — second test run; SQLAlchemy raised `NoForeignKeysError: Could not determine join condition between User and Note — there are no foreign keys linking these tables`
- **Issue:** `User.notes` relationship was defined in `app/auth/models.py` but the notes table has no `user_id` FK column yet (that FK is added in Plan 02/03 via the `add_user_id_to_notes` migration).
- **Fix:** Removed `User.notes` relationship from Plan 01. Relationship will be added in Plan 02/03 when the FK migration runs.
- **Files modified:** `app/auth/models.py`
- **Commit:** 00403bd

**3. [Rule 1 - Bug] Pre-existing mypy errors in notes package blocking `mypy app/auth/`**
- **Found during:** Task 3 — mypy check; two errors in `app/notes/` files pulled in transitively.
- **Issue 1:** `app/notes/repository.py:21` — unused `# type: ignore[type-arg]` comment (mypy version evolution made the ignore stale).
- **Issue 2:** `app/notes/service.py:71` — `list[Note]` passed where `list[NoteRead]` expected in `NoteListResponse(items=items, ...)`.
- **Fix 1:** Added `datetime` import; changed type annotation to `dict[str, InstrumentedAttribute[datetime]]`.
- **Fix 2:** Changed `items=items` to `items=[NoteRead.model_validate(n) for n in items]`; added `NoteRead` to service imports.
- **Files modified:** `app/notes/repository.py`, `app/notes/service.py`
- **Commit:** 00403bd

**4. [Rule 1 - Bug] Ruff lint issues — 5 auto-fixed + 2 manual**
- `UP017`: `timezone.utc` → `UTC` alias in service.py (auto-fixed by ruff --fix)
- `I001`: Import ordering in `alembic/env.py` and `tests/test_auth.py` (auto-fixed)
- `E402`: Missing noqa on auth model import in alembic/env.py (manual fix)
- `B904`: Missing `from exc` on `raise HTTPException` inside `except IntegrityError` (manual fix)

## Known Stubs

Two test methods skipped with `@pytest.mark.skip(reason="Plan 02 — ...")`:
- `test_refresh_rotation` — implements D-04; Plan 02 will add `POST /auth/refresh`
- `test_logout_revokes_token` — implements D-05; Plan 02 will add `POST /auth/logout`

These are intentional placeholders, not real stubs. The repository methods (`create_refresh_token`, `get_refresh_token_by_jti`, `revoke_refresh_token`) and schemas (`RefreshRequest`, `LogoutRequest`) are fully implemented — they're just not yet exercised by a route.

## Threat Surface

All new endpoints and patterns are within the plan's `<threat_model>`:

| Mitigation | Status |
|------------|--------|
| T-03-01: hashed_password never in UserRead response | Enforced at schema layer; asserted in test_register_returns_201 |
| T-03-02: constant-time verify; same 401 message for unknown email and wrong password | `password_hash.verify()` is Argon2id constant-time; both branches raise identical HTTPException |
| T-03-03: Weak password → 422 | `@field_validator` in UserCreate; 4 tests cover all composition cases |
| T-03-04: JWT secret via .env, not in code | jwt_secret_key read from Settings; default is placeholder only |
| T-03-05: HS256 signed access token, sub+exp only | create_access_token encodes only sub and exp |
| T-03-06/SC: Package legitimacy | Human-approved in Task 1 checkpoint |

## Self-Check: PASSED

All created/modified files exist on disk. All three task commits found in git history:
- `92219ee` — chore(03-01): install pyjwt/pwdlib/pydantic[email] and add JWT settings
- `6e4179d` — test(03-01): add failing tests for auth register and login endpoints (RED)
- `00403bd` — feat(03-01): implement app/auth/ package — register and login endpoints (GREEN)
