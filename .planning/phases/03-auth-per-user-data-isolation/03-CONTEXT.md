# Phase 3: Auth + Per-User Data Isolation - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers **multi-user JWT authentication and strict per-user data isolation**. Users can register and log in; every request is authenticated via a short-lived access token plus a rotating refresh token; and every note query is scoped so a user can only ever see or touch their own notes.

In scope:
- A `users` table and a `refresh_tokens` table (Alembic migration, `utf8mb4`)
- `POST /auth/register` → 201 (email + password)
- `POST /auth/login` → 15-min access token + a rotating refresh token
- `POST /auth/refresh` → new access token; rotates and invalidates the old refresh token
- `POST /auth/logout` → revoke the presented refresh token (204)
- A `get_current_user` dependency that protects the notes endpoints (401 on missing/expired token)
- `user_id` FK added to `notes`; all note reads/writes scoped to the authenticated user
- Cross-user access returns **403** (existing note owned by someone else); truly missing id returns **404**
- Tests proving cross-user isolation and the full token lifecycle, against real MySQL (testcontainers, established Phase 2 pattern)

Maps to requirements: **AUTH-01, AUTH-02, AUTH-03, AUTH-04**.

Out of scope (later phases / deferred): tags, collections, FULLTEXT search (Phase 4); local/cloud AI (Phases 5–6); CI pipeline + prod environment (Phase 7). Also explicitly deferred this phase: password reset, email verification, roles/permissions, OAuth/social login, and refresh-token family/cascade reuse detection.

</domain>

<decisions>
## Implementation Decisions

### Tokens & Sessions
- **D-01:** **Access token** is a signed JWT, **15-minute expiry**, **HS256** (ROADMAP-locked). Secret + expiries read from settings/`.env` (`JWT_SECRET_KEY`, etc.).
- **D-02:** **Refresh token is itself a signed JWT** carrying a **`jti` (uuid) claim** and a **7-day expiry**. The `jti` is persisted in the `refresh_tokens` table so individual tokens can be revoked (the JWT signature/exp is verified *and* the jti must be present-and-not-revoked in the DB).
- **D-03:** **Multiple concurrent refresh tokens per user** — each login creates an independent `refresh_tokens` row, so the same user can be authenticated from several clients at once. Refreshing one token rotates only that token's jti; others are untouched.
- **D-04:** **Rotation on refresh:** `POST /auth/refresh` verifies the presented refresh token, **revokes its old jti, and issues a new refresh token (new jti)** alongside the new access token.
- **D-05:** **Logout:** `POST /auth/logout` takes the refresh token, marks its jti revoked → **204**. A subsequent `/auth/refresh` with that token → **401**.
- **D-06:** **Reuse handling is minimal (rotation only):** replaying an already-rotated/revoked jti simply fails with **401**. No token-family/cascade revocation this phase (deferred as a later hardening step).

### Per-User Data Isolation (AUTH-04)
- **D-07:** Add a **`user_id` FK on `notes`** (`NOT NULL`, indexed, FK → `users.id`). Notes are owned by exactly one user.
- **D-08:** **Cross-user access returns 403, missing returns 404.** For single-note endpoints (`GET/PUT/DELETE /notes/{id}`): fetch the row by id first → if it doesn't exist, **404**; if it exists but `owner != current_user`, **403 Forbidden**. (This is a deliberate, explicit ownership check rather than 404-hiding — chosen for the teachable HTTP-semantics value.)
- **D-09:** **List endpoints are user-scoped** — `GET /notes` only ever returns the authenticated user's notes (`WHERE user_id = current_user`). The Phase-2 pagination/sort/filter contract is preserved, just narrowed to the owner.
- **D-10:** **Note creation** assigns `user_id = current_user` server-side (never accepted from the client body).

### Migration Strategy
- **D-11:** Add `user_id` as a **clean `NOT NULL` FK** in a new Alembic migration. **Dev notes data is reset/truncated** — Phase 2 just shipped and there is no real data to preserve, so no seed-user backfill step is needed.

### Registration & Login Policy
- **D-12:** **Email validated with Pydantic `EmailStr`** (adds the `email-validator` dependency, pulled via `pydantic[email]`). Malformed email → 422 at the schema layer.
- **D-13:** **Password policy: minimum 8 characters AND a composition rule** (at least one uppercase, one lowercase, one digit, one symbol), enforced via a Pydantic `@field_validator` → 422 on violation. (Length-only was offered; user chose length + composition.)
- **D-14:** **Duplicate email → 409 Conflict.** `users.email` has a **UNIQUE index**; the service catches the unique-constraint violation and raises HTTP 409 ("Email already registered"). Not 422.

### Claude's Discretion (sensible defaults — planner may refine)
- **`users` table shape:** `id` (BIGINT UNSIGNED PK, mirroring the notes PK convention), `email` (VARCHAR UNIQUE, `utf8mb4`), `hashed_password`, `created_at` (server default). `updated_at` optional.
- **Password hashing:** **pwdlib[argon2]** (Argon2id) — stack-locked in CLAUDE.md (NOT passlib).
- **JWT library:** **PyJWT** (`import jwt`) — stack-locked (NOT python-jose).
- **Login transport:** login accepts a **JSON body** `{email, password}` and returns `{access_token, refresh_token, token_type: "bearer"}`. (If the planner prefers `OAuth2PasswordRequestForm` for tighter Swagger "Authorize" integration, that's acceptable — but JSON body is the API-first default here.)
- **Bearer scheme:** protect routes with FastAPI **`HTTPBearer`** (or `OAuth2`) so Swagger's "Authorize" button works and `get_current_user` reads the `Authorization: Bearer <access>` header.
- **`get_current_user` placement:** add to `app/core/dependencies.py` (the established DI home); a new `app/auth/` domain package holds router/schemas/models/service/repository, mirroring `app/notes/`.
- **`refresh_tokens` row fields:** `jti`, `user_id` FK, `expires_at`, `revoked`/`revoked_at` (exact columns are the planner's call; must support rotation + per-token revocation).
- Whether refresh-token rotation deletes-and-reinserts the row or flips a `revoked` flag + inserts a new row — either satisfies D-04.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — product context; "Sécurité: Auth JWT multi-utilisateur avec isolation des données; secrets hors du repo"
- `.planning/REQUIREMENTS.md` — AUTH-01..04 are the requirements in scope this phase
- `.planning/ROADMAP.md` §"Phase 3: Auth + Per-User Data Isolation" — the 5 success criteria this phase is judged against (register→201, login→15-min access + rotating refresh in `refresh_tokens`, refresh rotation+invalidation, cross-user 403/404, 401 on no/expired token)
- `CLAUDE.md` §"JWT Auth: PyJWT + pwdlib" and "What NOT to Use" — **PyJWT (not python-jose)**, **pwdlib[argon2] (not passlib)** are mandatory

### Research
- `.planning/research/ARCHITECTURE.md` — domain-per-folder layering (Router → Service → Repository); mirror it for a new `app/auth/` package
- `.planning/research/STACK.md` — async SQLAlchemy/asyncmy patterns, pytest-asyncio + httpx AsyncClient testing
- `.planning/research/PITFALLS.md` — secrets-at-runtime, async engine pitfalls

### Phase 2 carry-forward (the integration foundation this phase builds on)
- `.planning/phases/02-database-api-skeleton/02-CONTEXT.md` — D-10 domain-per-folder, D-12 thin service layer (the seam where auth scoping was always intended to land), D-14 async DB layer, D-16/17/18 testcontainers test strategy

### Existing code (integration targets)
- `app/notes/models.py` — add the `user_id` FK here (the file already documents this as the Phase-3 seam)
- `app/notes/{router,service,schemas,repository}.py` — `current_user` injection + `user_id` filtering land here (seams already marked in comments)
- `app/core/dependencies.py` — add `get_current_user`; this is also where `get_db` / `get_note_service` live
- `app/core/config.py` — add `jwt_secret_key`, token-expiry settings; `extra="ignore"` already tolerates them
- `app/main.py` — register the new `auth` router
- `app/database.py` — shared async engine/session/`Base` (new `User` / `RefreshToken` models extend `Base`)
- `tests/conftest.py`, `tests/test_notes_crud.py`, `tests/test_notes_list.py` — testcontainers MySQL harness + transaction-rollback pattern to extend with auth fixtures and cross-user isolation tests
- `.env.example` — already carries JWT placeholders (per Phase 1); confirm/extend `JWT_SECRET_KEY` + expiry vars

No user-referenced external docs/ADRs were introduced during discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/notes/` package** is the exact template for a new **`app/auth/`** package (router/schemas/models/service/repository) — domain-per-folder is the established convention.
- **`app/core/dependencies.py`** already centralizes `Depends()` providers and is designed for clean test overrides — `get_current_user` belongs here, and notes handlers will depend on it.
- **`tests/conftest.py`** testcontainers `mysql:8.4` + `alembic upgrade head` + transaction-per-test rollback — reuse directly; add fixtures that create users and issue tokens.
- **`pyproject.toml`** — `asyncio_mode = "auto"` already set; add deps `pyjwt`, `pwdlib[argon2]`, `pydantic[email]` (email-validator).

### Established Patterns
- **Router → Service → Repository**, zero business logic in routers — auth (hashing, token issue/verify/rotate) lives in an `AuthService`; all SQL in repositories.
- **Alembic migrations, never `Base.metadata.create_all()`** — the `users` / `refresh_tokens` tables + the `notes.user_id` FK all come via migration.
- **Secrets at runtime via `.env`** — `JWT_SECRET_KEY` never baked into images or committed.
- **utf8mb4 / InnoDB** table conventions (mirror `notes` model `__table_args__`).

### Integration Points
- `notes` queries change shape: every read/write gains a `user_id` predicate; single-item endpoints add the ownership check (404 vs 403).
- `app/main.py` registers the `auth` router alongside `notes` and `health`.
- The Phase-2 note tests must be updated to authenticate (they currently hit open endpoints) — expect to thread a token/fixture through them.

</code_context>

<specifics>
## Specific Ideas

- This is a **learning project** — choices lean toward the teachable-correct path even when slightly more work (e.g., JWT-as-refresh with a `jti` to learn claims + DB-backed revocation together; explicit 403 ownership checks; password composition validator; 409 semantics).
- The full token lifecycle must actually work end-to-end via Swagger: register → login → Authorize with the access token → call `/notes` → refresh → logout → refreshing the logged-out token fails with 401.
- Cross-user isolation must be proven by an **integration test** (user A cannot read/update/delete user B's note: 403; lists never bleed across users), against real MySQL — not mocked.

</specifics>

<deferred>
## Deferred Ideas

- **Refresh-token family / cascade reuse detection** (revoke all of a login's descendants on replay of a revoked token) — a later security-hardening step; minimal rotation-only handling this phase (D-06).
- **Password reset / forgot-password flow** — not in AUTH-01..04; future phase.
- **Email verification on signup** — not required this phase.
- **Roles / permissions / admin** — single flat user model for now; no RBAC.
- **OAuth / social login (Google, GitHub)** — out of scope for the learning objective.
- **Rate limiting / brute-force lockout on login** — sensible later hardening, not in scope now.

None of the above is scope creep into Phase 3 — they are correctly sequenced out.

</deferred>

---

*Phase: 3-Auth + Per-User Data Isolation*
*Context gathered: 2026-06-24*
