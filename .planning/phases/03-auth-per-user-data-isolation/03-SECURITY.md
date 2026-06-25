# SECURITY.md — Phase 03: Auth + Per-User Data Isolation

**Audit date:** 2026-06-25
**Phase:** 03 — auth-per-user-data-isolation
**ASVS Level:** 2
**Plans audited:** 03-01, 03-02, 03-03
**Threats closed:** 21 / 21
**Threats open (BLOCKER):** 0
**Unregistered flags:** 0

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-03-01 | Information Disclosure | mitigate | CLOSED | `app/auth/service.py:34` — `PasswordHash.recommended()` (Argon2id). `app/auth/schemas.py:49-59` — `UserRead` has no `hashed_password` field. `tests/test_auth.py:65-66` — asserts `"hashed_password" not in body` and `"password" not in body`. |
| T-03-02 | Information Disclosure | mitigate | CLOSED | `app/auth/service.py:112-128` — single `invalid_credentials` exception instance raised on both unknown-email and wrong-password paths. `service.py:40` — `_DUMMY_PASSWORD_HASH` forces one Argon2id verify on the no-user path (timing equalisation), preventing user-enumeration via response latency. |
| T-03-03 | Elevation of Privilege | mitigate | CLOSED | `app/auth/schemas.py:32-46` — `@field_validator("password")` enforces len>=8 + uppercase + lowercase + digit + symbol via `re.search`. Raises `ValueError` → FastAPI 422. Covered by 4 tests in `tests/test_auth.py:89-122`. |
| T-03-04 | Information Disclosure | mitigate | CLOSED | `app/core/config.py:17-30` — `jwt_secret_key` field loaded from env via `pydantic-settings` `BaseSettings`; never hard-coded in router, service, or Dockerfile. Additional defence-in-depth: `config.py:35-54` — `@model_validator` refuses to start with the known-insecure default or any key shorter than 32 bytes outside `environment="development"`. |
| T-03-05 | Spoofing | mitigate | CLOSED | `app/auth/service.py:48-54` — `create_access_token` encodes only `sub` (str user_id) and `exp`; no email, role, or mutable claim. Algorithm is explicitly `"HS256"`. `tests/test_auth.py:181-187` — decodes token and asserts `payload["sub"] == str(user_id)` and `"exp" in payload`. |
| T-03-06 | Tampering | mitigate | CLOSED | Process/supply-chain checkpoint. `03-01-SUMMARY.md` records human approval of PyJWT, pwdlib[argon2], and email-validator before install (Task 1 gate). Not runtime-verifiable by design; evidence is the SUMMARY record and commit `92219ee`. |
| T-03-SC | Tampering | mitigate | CLOSED | Same evidence as T-03-06: blocking-human checkpoint executed in Plan 01 Task 1. PyPI pages for all three packages were verified against known legitimate authors before `uv add` ran. |
| T-03-07 | Repudiation | accept | CLOSED | See "Accepted Risks" section below. |
| T-03-08 | Spoofing | mitigate | CLOSED | `app/core/dependencies.py:41` — `bearer_scheme = HTTPBearer(auto_error=False)`. `dependencies.py:80-81` — explicit `if credentials is None: raise credentials_exception` (HTTP 401). HS256 signature verified by `jwt.decode` at `dependencies.py:84-88`. `tests/test_auth.py:195-203` — `test_no_token_returns_401` asserts 401 (not 403). |
| T-03-09 | Elevation of Privilege | mitigate | CLOSED | `app/core/dependencies.py:89-91` — `except (ExpiredSignatureError, InvalidTokenError) as exc: raise credentials_exception` (HTTP 401). `jwt.decode` validates `exp` automatically. `tests/test_auth.py:215-230` — `test_expired_token_returns_401` crafts a past-exp token and asserts 401. |
| T-03-10 | Repudiation / Replay | mitigate | CLOSED | `app/auth/repository.py:117-143` — `revoke_refresh_token_if_active` issues `UPDATE … WHERE jti=:jti AND revoked=0`; atomically prevents replay races (rowcount==0 → 401). `app/auth/service.py:222-224` — checks rowcount and raises 401 if 0. `tests/test_auth.py:328-341` — `test_old_refresh_token_revoked_after_rotation` asserts replayed token returns 401. |
| T-03-11 | Elevation of Privilege | mitigate | CLOSED | `app/auth/service.py:278-280` — `logout` looks up jti via `get_refresh_token_by_jti` and calls `revoke_refresh_token` (sets `revoked=True`). `tests/test_auth.py:417-428` — `test_logout_then_refresh_returns_401` asserts 401 after logout. |
| T-03-12 | Elevation of Privilege | mitigate | CLOSED | `app/core/dependencies.py:106-108` — `user = await AuthRepository(db).get_user_by_id(user_id); if user is None: raise credentials_exception` (HTTP 401). `tests/test_auth.py:290-304` — `test_token_for_deleted_user_returns_401` passes non-existent user_id (999999) and asserts 401. |
| T-03-13 | Information Disclosure | mitigate | CLOSED | `app/auth/service.py:48-54` — access token payload contains only `sub` and `exp`. `app/auth/service.py:63-72` — refresh token payload contains only `sub`, `jti`, and `exp`. No email, role, or mutable attribute in either token. `app/core/dependencies.py:93-94` — only `sub` is extracted from the payload; all user attributes are fetched from DB. |
| T-03-14 | Elevation of Privilege | accept | CLOSED | See "Accepted Risks" section below. |
| T-03-15 | Information Disclosure | mitigate | CLOSED | `app/notes/service.py:44-67` — `get_or_404_owned` fetches by PK, raises HTTP 404 if None, raises HTTP 403 if `note.user_id != current_user.id`. `tests/test_notes_isolation.py:48-60` — `test_cross_user_get_returns_403` asserts 403. |
| T-03-16 | Information Disclosure | mitigate | CLOSED | `app/notes/repository.py:106` — `query = query.where(Note.user_id == user_id)` applied before optional content filter; both count subquery and page query are owner-scoped. `tests/test_notes_isolation.py:106-134` — `test_list_isolation` asserts neither user sees the other's notes. |
| T-03-17 | Tampering | mitigate | CLOSED | `app/notes/schemas.py` — `NoteCreate` fields are `title`, `content`, `source_url` only; no `user_id` field. `app/notes/router.py:89` — `user_id=current_user.id` assigned server-side. `tests/test_notes_isolation.py:142-166` — `test_create_assigns_owner` posts `user_id: 9999` in body and confirms it is ignored; response `user_id` equals authenticated user's real id. |
| T-03-18 | Spoofing | mitigate | CLOSED | `app/notes/router.py:64,81,106,127,147` — all 5 handlers carry `current_user: User = Depends(get_current_user)` (5 matches confirmed by grep). `tests/test_notes_isolation.py:25-42` — `test_create/get/list_notes_requires_auth` each assert 401 on missing token. |
| T-03-19 | Elevation of Privilege | mitigate | CLOSED | `app/notes/service.py:120,128` — `update` and `delete` both call `get_or_404_owned(note_id, current_user)` which raises HTTP 403 on wrong owner. `tests/test_notes_isolation.py:63-86` — `test_cross_user_put_returns_403` and `test_cross_user_delete_returns_403` both assert 403. |
| T-03-20 | Tampering | mitigate | CLOSED | `alembic/versions/0003_add_user_id_to_notes.py:36` — `op.execute("TRUNCATE TABLE notes")` before column addition. `0003_add_user_id_to_notes.py:28` — `down_revision = "a1b2c3d4e5f6"` (chains to the create_users_and_refresh_tokens migration, ensuring users table exists first). FK declared with `ondelete="CASCADE"` at `0003_add_user_id_to_notes.py:58`. |
| T-03-21 | Information Disclosure | accept | CLOSED | See "Accepted Risks" section below. |

---

## Accepted Risks

| Threat ID | Category | Accepted Behavior | Rationale |
|-----------|----------|-------------------|-----------|
| T-03-07 | Repudiation | `POST /auth/register` returns HTTP 409 with detail "Email already registered" on duplicate email, revealing whether an address is registered. | Deliberate design choice for this learning project (D-14). Rate limiting is deferred (D-06 scope). Acceptable for a self-hosted personal knowledge base with a small, known user base. |
| T-03-14 | Elevation of Privilege | Refreshing one of a user's concurrent refresh tokens revokes only that token's jti; sibling tokens remain valid. Family/cascade reuse-detection is not implemented. | D-03 decision: concurrent sessions are independent. A stolen refresh token is a separate threat from replay of a specific token. Cascade revocation deferred (D-06). Verified as intentional by `tests/test_auth.py:431-449` (`test_other_refresh_tokens_unaffected_by_rotation`). |
| T-03-21 | Information Disclosure | `GET/PUT/DELETE /notes/{id}` for a note owned by another user returns HTTP 403 (not 404-hiding). This confirms to the caller that a note with that id exists. | Deliberate HTTP semantics for teachable correctness (D-08). The alternative (404-hiding) would misrepresent the resource state. Acceptable given the authenticated context (caller must already have a valid JWT). |

---

## Unregistered Flags

None. No `## Threat Flags` sections were present in any of the three SUMMARY files. No new attack surface was detected during implementation that lacks a threat mapping.

---

## Notes on Implementation Quality

The following security-relevant implementation details go beyond the declared mitigations and represent defence-in-depth not required by the threat register:

- **T-03-02 strengthened** — The implementation adds `_DUMMY_PASSWORD_HASH` (`service.py:40`) and performs a full Argon2id verify on the no-user path, eliminating the timing oracle entirely. The plan only required returning the same 401 message.
- **T-03-04 strengthened** — `config.py:35-54` adds a `@model_validator` that refuses startup with the known-insecure default JWT secret or any key shorter than 32 bytes outside `development` mode. The plan only required reading the secret from env.
- **T-03-10 strengthened** — Rotation uses a single atomic conditional `UPDATE … WHERE revoked=0` (`repository.py:117-143`) rather than a read-then-write, closing the concurrent-refresh race window. The plan only required jti revocation on rotation.
- **T-03-03** — All four composition failure modes (too short, no uppercase, no digit, no symbol) are individually tested.

---

*Audit performed against branch: `gsd/phase-03-auth-per-user-data-isolation`*
*Auditor: gsd-security-auditor (automated) — 2026-06-25*
