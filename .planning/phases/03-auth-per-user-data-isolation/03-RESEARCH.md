# Phase 3: Auth + Per-User Data Isolation - Research

**Researched:** 2026-06-25
**Domain:** JWT authentication, refresh token rotation, per-user data isolation, FastAPI security, Alembic FK migrations
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tokens & Sessions**
- **D-01:** Access token is a signed JWT, 15-minute expiry, HS256. Secret + expiries read from settings/`.env` (`JWT_SECRET_KEY`, etc.).
- **D-02:** Refresh token is itself a signed JWT carrying a `jti` (uuid) claim and a 7-day expiry. The `jti` is persisted in the `refresh_tokens` table so individual tokens can be revoked (JWT signature/exp verified AND jti must be present-and-not-revoked in DB).
- **D-03:** Multiple concurrent refresh tokens per user — each login creates an independent `refresh_tokens` row. Refreshing one token rotates only that token's jti; others are untouched.
- **D-04:** Rotation on refresh: `POST /auth/refresh` verifies the presented refresh token, revokes its old jti, and issues a new refresh token (new jti) alongside the new access token.
- **D-05:** Logout: `POST /auth/logout` takes the refresh token, marks its jti revoked → 204. A subsequent `/auth/refresh` with that token → 401.
- **D-06:** Reuse handling is minimal (rotation only): replaying an already-rotated/revoked jti simply fails with 401. No token-family/cascade revocation this phase (deferred).

**Per-User Data Isolation (AUTH-04)**
- **D-07:** Add a `user_id` FK on `notes` (NOT NULL, indexed, FK → `users.id`). Notes are owned by exactly one user.
- **D-08:** Cross-user access returns 403, missing returns 404. For single-note endpoints: fetch by id first → if it doesn't exist, 404; if it exists but owner != current_user, 403.
- **D-09:** List endpoints are user-scoped — `GET /notes` only ever returns the authenticated user's notes. Phase-2 pagination/sort/filter contract preserved.
- **D-10:** Note creation assigns `user_id = current_user` server-side (never accepted from the client body).

**Migration Strategy**
- **D-11:** Add `user_id` as a clean NOT NULL FK in a new Alembic migration. Dev notes data is reset/truncated — no seed-user backfill needed.

**Registration & Login Policy**
- **D-12:** Email validated with Pydantic `EmailStr` (adds `email-validator` dependency via `pydantic[email]`). Malformed email → 422.
- **D-13:** Password policy: minimum 8 characters AND composition rule (at least one uppercase, lowercase, digit, symbol), enforced via Pydantic `@field_validator` → 422 on violation.
- **D-14:** Duplicate email → 409 Conflict. `users.email` has a UNIQUE index; service catches unique-constraint violation and raises HTTP 409.

### Claude's Discretion (sensible defaults — planner may refine)
- `users` table shape: `id` (BIGINT UNSIGNED PK), `email` (VARCHAR UNIQUE, utf8mb4), `hashed_password`, `created_at` (server default). `updated_at` optional.
- Password hashing: **pwdlib[argon2]** (Argon2id) — stack-locked in CLAUDE.md.
- JWT library: **PyJWT** (`import jwt`) — stack-locked.
- Login transport: JSON body `{email, password}` → `{access_token, refresh_token, token_type: "bearer"}`.
- Bearer scheme: FastAPI `HTTPBearer` (or `OAuth2`) for Swagger "Authorize" button and `get_current_user` reading `Authorization: Bearer <access>` header.
- `get_current_user` placement: `app/core/dependencies.py`.
- New `app/auth/` domain package: router/schemas/models/service/repository, mirroring `app/notes/`.
- `refresh_tokens` row fields: `jti`, `user_id` FK, `expires_at`, `revoked`/`revoked_at`. Rotation may delete-and-reinsert or flip a `revoked` flag + insert a new row.

### Deferred Ideas (OUT OF SCOPE)
- Refresh-token family / cascade reuse detection (revoke all of a login's descendants on replay of a revoked token)
- Password reset / forgot-password flow
- Email verification on signup
- Roles / permissions / admin (RBAC)
- OAuth / social login (Google, GitHub)
- Rate limiting / brute-force lockout on login
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can sign up with an email and password | pwdlib[argon2] hashing + Pydantic EmailStr + @field_validator for password composition + 409 on duplicate |
| AUTH-02 | User can log in and receive a JWT access token | PyJWT HS256 encode with `sub`/`exp` claims + pwdlib.verify + JSON body login |
| AUTH-03 | User stays authenticated across requests, with token refresh (no re-login each call) | JWT refresh token as signed JWT with `jti` + DB revocation table + POST /auth/refresh rotation |
| AUTH-04 | User can only access their own data — every query is scoped to the authenticated user | `user_id` FK on notes + `get_current_user` dependency + 403-vs-404 ownership check |
</phase_requirements>

---

## Summary

Phase 3 adds multi-user JWT authentication and strict per-user data isolation to the existing Phase 2 FastAPI + MySQL skeleton. The authentication model uses short-lived access tokens (JWT, HS256, 15-min) combined with rotating refresh tokens (also JWT, carrying a `jti` UUID claim, 7-day expiry) whose `jti` values are persisted in a `refresh_tokens` DB table for individual revocation.

The entire stack (PyJWT, pwdlib[argon2], FastAPI HTTPBearer, SQLAlchemy 2 async with Mapped types) is already researched and stack-locked in CLAUDE.md. The main implementation work is: (1) the `app/auth/` domain package mirroring `app/notes/`, (2) a two-migration Alembic sequence (users + refresh_tokens tables, then user_id FK on notes with a TRUNCATE step), (3) threading `get_current_user` through the notes domain (router, service, repository), and (4) integration tests proving cross-user isolation against real MySQL.

The `notes` table migration requires special attention: D-11 specifies NOT NULL with no backfill, which means the migration must TRUNCATE `notes` before adding the NOT NULL FK column. This is safe because Phase 2 has no real data. The testcontainer harness (session-scoped MySQL + alembic upgrade head + per-test rollback) is already established in Phase 2 and only needs auth fixtures added.

**Primary recommendation:** Follow the locked decisions exactly. New package additions are `pyjwt`, `pwdlib[argon2]`, and `pydantic[email]` — all verified on PyPI as mature, well-maintained packages. The `app/auth/` package structure should mirror `app/notes/` exactly for architectural consistency.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password hashing (register) | API / Backend (AuthService) | — | Hashing is a server-side secret operation; never in DB or client |
| JWT issuance (login/refresh) | API / Backend (AuthService) | — | Signing requires the `JWT_SECRET_KEY` — backend only |
| Bearer token extraction | API / Backend (HTTPBearer dependency) | — | FastAPI security scheme reads `Authorization` header |
| Token validation (access) | API / Backend (get_current_user dep) | — | Stateless: signature + exp verify in-process, no DB hit |
| Refresh token DB lookup | API / Backend (AuthRepository) | Database / Storage | jti must be checked in `refresh_tokens` table — requires DB |
| Per-user note scoping | API / Backend (NoteRepository) | Database / Storage | `WHERE user_id = current_user.id` lives in every query |
| Ownership check (403 vs 404) | API / Backend (NoteService) | — | Business rule: fetch note, check owner, raise appropriate error |
| `refresh_tokens` table | Database / Storage | — | Persistence for revocable jti values |
| `users` table | Database / Storage | — | Auth identity anchor for all user-owned entities |
| Pydantic email/password validation | API / Backend (schemas) | — | Schemas live in the API tier; 422 is FastAPI's job |

---

## Standard Stack

### Core (all stack-locked in CLAUDE.md)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.13.0 (latest) | JWT encode/decode HS256 | Stack-locked. Official FastAPI tutorial uses PyJWT directly. Import as `import jwt`. 603M downloads/month. [VERIFIED: PyPI registry + official FastAPI docs] |
| pwdlib[argon2] | 0.3.0 (latest) | Argon2id password hashing | Stack-locked. Modern replacement for unmaintained passlib. FastAPI-Users migrated to pwdlib. 2.8M downloads/month. [VERIFIED: PyPI registry + frankie567.github.io/pwdlib/] |
| pydantic[email] | bundled with FastAPI | EmailStr validation | Pulls `email-validator` 2.3.0 (latest) as extra dep. Required for D-12. [VERIFIED: PyPI registry] |
| FastAPI HTTPBearer | FastAPI 0.115.x | Bearer token extraction | Built-in security scheme — reads `Authorization: Bearer <token>` header, returns `HTTPAuthorizationCredentials`. No extra install. [VERIFIED: fastapi.tiangolo.com/reference/security/] |

### Already Installed (no new installs needed)

| Library | Purpose | Phase 3 Use |
|---------|---------|-------------|
| SQLAlchemy 2.x | ORM | User + RefreshToken models, FK relations, async queries |
| Alembic 1.18.4 | DB migrations | 2 new migrations (users+refresh_tokens, notes.user_id FK) |
| pydantic-settings 2.x | Config | Add JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS |
| asyncmy 0.2.x | MySQL driver | Unchanged |
| pytest + pytest-asyncio | Testing | Auth fixtures + cross-user isolation tests |
| httpx | Test client | `AsyncClient` already in conftest.py |

### New Packages to Install

```bash
uv add pyjwt "pwdlib[argon2]" "pydantic[email]"
```

---

## Package Legitimacy Audit

> slopcheck was not available in this environment. Packages verified via PyPI API, download statistics, and official documentation cross-reference.

| Package | Registry | Age | Downloads/mo | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-------------|-------------|-----------|-------------|
| PyJWT | PyPI | ~12 yrs | ~603M | github.com/jpadilla/pyjwt | [ASSUMED-OK: not run] | Approved — referenced in FastAPI official tutorial, massive downloads |
| pwdlib | PyPI | ~2 yrs | ~2.8M | github.com/frankie567/pwdlib | [ASSUMED-OK: not run] | Approved — official FastAPI migration from passlib; referenced in FastAPI docs |
| email-validator | PyPI | ~8 yrs | ~199M | (Pydantic officially depends on it) | [ASSUMED-OK: not run] | Approved — Pydantic's official email validation extra |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*slopcheck was unavailable at research time. All packages are tagged [ASSUMED-OK] based on download volume, age, official documentation references, and registry presence. If the planner wishes to gate these, add a `checkpoint:human-verify` before `uv add`.*

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Client
    │
    │  POST /auth/register  {email, password}
    │  POST /auth/login     {email, password}
    │  POST /auth/refresh   {refresh_token}
    │  POST /auth/logout    {refresh_token}
    │  GET  /notes/         Authorization: Bearer <access_token>
    │
    ▼
FastAPI App (app/main.py)
    │
    ├── app/auth/router.py ──────────────────────────────────────────┐
    │       │                                                          │
    │       ▼                                                          │
    │   AuthService (app/auth/service.py)                             │
    │       │  hash_password() / verify_password()                    │
    │       │  create_access_token() / create_refresh_token()         │
    │       │  verify_token() / extract_jti()                         │
    │       │                                                          │
    │       ▼                                                          │
    │   AuthRepository (app/auth/repository.py)                       │
    │       │  create_user()          → INSERT users                   │
    │       │  get_user_by_email()    → SELECT users WHERE email=      │
    │       │  create_refresh_token() → INSERT refresh_tokens          │
    │       │  get_refresh_token()    → SELECT refresh_tokens WHERE jti= (active)
    │       │  revoke_refresh_token() → UPDATE refresh_tokens SET revoked=True
    │       │                                                          │
    │       └─────────────────────────────── MySQL 8.4 ───────────────┘
    │                                         users table
    │                                         refresh_tokens table
    │
    ├── app/core/dependencies.py
    │       │  get_current_user(token: HTTPAuthorizationCredentials)
    │       │      → jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    │       │      → extract sub (user_id)
    │       │      → 401 if expired / invalid
    │       │      → return User ORM object
    │       │
    ├── app/notes/router.py ─────── Depends(get_current_user) ──────→ current_user injected
    │       │
    │       ▼
    │   NoteService (app/notes/service.py)
    │       │  create(data, user_id=current_user.id)
    │       │  get_or_404_owned(note_id, current_user)
    │       │      → fetch by id → 404 if not found
    │       │      → 403 if note.user_id != current_user.id
    │       │
    │       ▼
    │   NoteRepository (app/notes/repository.py)
    │       │  create(data, user_id)     → INSERT WITH user_id
    │       │  get_by_id(note_id)        → SELECT by PK (no user filter here)
    │       │  list_paginated(user_id, ..) → SELECT WHERE user_id=
    │       │  update(note, data)
    │       │  delete(note)
    │       │
    │       └───────────────────────────── MySQL 8.4 ─── notes table (user_id FK)
    │
    └── app/api/health.py (unchanged)
```

### Recommended Project Structure

The new `app/auth/` package mirrors `app/notes/` exactly:

```
app/
├── auth/                    # New domain package (Phase 3)
│   ├── __init__.py
│   ├── models.py            # User, RefreshToken ORM models
│   ├── schemas.py           # UserCreate, UserRead, LoginRequest, TokenResponse, RefreshRequest
│   ├── repository.py        # AuthRepository: user + refresh_token SQL
│   ├── service.py           # AuthService: hashing, JWT issuance, rotation logic
│   └── router.py            # POST /auth/register, /login, /refresh, /logout
├── core/
│   ├── config.py            # Add: jwt_secret_key, access_token_expire_minutes, refresh_token_expire_days
│   └── dependencies.py      # Add: get_current_user (HTTPBearer + jwt.decode)
├── notes/
│   ├── models.py            # Add: user_id FK column + relationship to User
│   ├── repository.py        # Add: user_id param to create(); WHERE user_id= on list
│   ├── service.py           # Add: get_or_404_owned(); pass user_id through
│   └── router.py            # Add: current_user = Depends(get_current_user) on all endpoints
└── main.py                  # Register auth router at /auth prefix
alembic/
└── versions/
    ├── d51191e92276_create_notes_table.py  (existing)
    ├── XXXX_create_users_and_refresh_tokens.py  (new)
    └── YYYY_add_user_id_to_notes.py             (new)
tests/
├── conftest.py              # Add: registered_user fixture, auth_client fixture
├── test_auth.py             # New: register, login, refresh, logout, 401 tests
├── test_notes_isolation.py  # New: cross-user 403/404, list isolation
├── test_notes_crud.py       # Existing: update to thread token through (add auth_client)
└── test_notes_list.py       # Existing: same
```

### Pattern 1: JWT Token Pair Issuance

**What:** Access token (short-lived, stateless) + refresh token (long-lived, jti stored in DB).
**When to use:** Every login creates a new pair; every `/auth/refresh` rotates the refresh token.

```python
# Source: pyjwt.readthedocs.io/en/stable/usage.html [VERIFIED: official PyJWT docs]
import jwt
import uuid
from datetime import datetime, timezone, timedelta

def create_access_token(user_id: int, secret: str, expire_minutes: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def create_refresh_token(user_id: int, secret: str, expire_days: int) -> tuple[str, str]:
    """Returns (token_str, jti) — jti must be stored in DB."""
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "exp": datetime.now(timezone.utc) + timedelta(days=expire_days),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, jti
```

### Pattern 2: get_current_user Dependency (FastAPI HTTPBearer)

**What:** FastAPI security scheme that reads `Authorization: Bearer <token>`, decodes it, and returns the current user.
**When to use:** As a `Depends()` on every protected route.

```python
# Source: fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ [VERIFIED: official FastAPI docs]
# Source: fastapi.tiangolo.com/reference/security/ [VERIFIED: official FastAPI docs]
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import jwt

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except (ExpiredSignatureError, InvalidTokenError):
        raise credentials_exception
    user = await user_repo.get_by_id(int(user_id), db)
    if user is None:
        raise credentials_exception
    return user
```

**Note on `auto_error=False`:** FastAPI 0.115.x returns 403 (not 401) when a missing/malformed Authorization header triggers `HTTPBearer` with `auto_error=True`. Using `auto_error=False` and checking for `None` manually gives us full control to raise 401. [VERIFIED: github.com/fastapi/fastapi/discussions/12384]

### Pattern 3: Refresh Token Rotation (D-04)

**What:** Verify the refresh token JWT + check jti in DB, revoke old jti, issue new pair.
**When to use:** `POST /auth/refresh` endpoint.

```python
# Derived from PyJWT docs + CONTEXT.md D-04 decision
async def rotate_refresh_token(refresh_token_str: str) -> tuple[str, str]:
    """Returns (new_access_token, new_refresh_token)."""
    try:
        payload = jwt.decode(refresh_token_str, settings.jwt_secret_key, algorithms=["HS256"])
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    jti = payload.get("jti")
    user_id = int(payload.get("sub"))
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # DB check: jti must exist and not be revoked
    token_record = await auth_repo.get_refresh_token_by_jti(jti, db)
    if token_record is None or token_record.revoked:
        raise HTTPException(status_code=401, detail="Refresh token revoked or not found")

    # Rotation: revoke old, issue new
    await auth_repo.revoke_refresh_token(jti, db)
    new_access = create_access_token(user_id, ...)
    new_refresh, new_jti = create_refresh_token(user_id, ...)
    await auth_repo.create_refresh_token(user_id, new_jti, expires_at, db)
    return new_access, new_refresh
```

### Pattern 4: Ownership Check (D-08) — 403 vs 404

**What:** For single-resource endpoints, fetch by ID first, then check ownership.
**When to use:** `GET/PUT/DELETE /notes/{note_id}` with auth.

```python
# Source: CONTEXT.md D-08 (teachable HTTP semantics choice)
async def get_or_404_owned(self, note_id: int, current_user: User) -> Note:
    note = await self._repo.get_by_id(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access forbidden")
    return note
```

### Pattern 5: SQLAlchemy 2 ORM Models with FK

**What:** User model with `BIGINT UNSIGNED PK`, RefreshToken with FK to users, Note with FK to users.

```python
# Source: docs.sqlalchemy.org/en/20/orm/basic_relationships.html [VERIFIED: official SQLAlchemy docs]
from sqlalchemy.dialects.mysql import INTEGER, BIGINT
from sqlalchemy import String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    notes: Mapped[list["Note"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }
    id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
```

### Pattern 6: Alembic Migration for user_id FK on Existing Table

**What:** D-11 says TRUNCATE is acceptable (no real data). Sequence: create new migration, TRUNCATE notes, add nullable column, populate if needed (no-op here), add FK constraint, alter to NOT NULL.

```python
# Source: alembic.sqlalchemy.org/en/latest/ops.html [VERIFIED: official Alembic docs]
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade() -> None:
    # D-11: Dev data is truncated — no backfill needed
    op.execute("TRUNCATE TABLE notes")

    # Step 1: Add nullable column first (required for existing table)
    op.add_column(
        "notes",
        sa.Column(
            "user_id",
            mysql.INTEGER(unsigned=True),
            nullable=True,
            comment="Owner user — Phase 3 auth seam",
        ),
    )
    # Step 2: Add FK constraint
    op.create_foreign_key(
        "fk_notes_user_id",
        "notes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Step 3: Make NOT NULL (safe because table is empty after TRUNCATE)
    op.alter_column("notes", "user_id", nullable=False)
    # Step 4: Add index for query performance
    op.create_index("ix_notes_user_id", "notes", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_constraint("fk_notes_user_id", "notes", type_="foreignkey")
    op.drop_column("notes", "user_id")
```

**Migration dependency chain:** Migration YYYY (`add_user_id_to_notes`) MUST have `down_revision = "XXXX"` where XXXX is the `create_users_and_refresh_tokens` migration. The `users` table must exist before the FK can be created.

### Pattern 7: pwdlib Argon2id Hashing

```python
# Source: frankie567.github.io/pwdlib/ [VERIFIED: official pwdlib docs]
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()  # Argon2id by default

# On registration
hashed = password_hash.hash(plain_password)

# On login
is_valid = password_hash.verify(plain_password, hashed)
```

### Pattern 8: Auth Test Fixtures

```python
# [ASSUMED] — pattern derived from Phase 2 conftest.py + FastAPI testing best practices
import pytest_asyncio
from httpx import AsyncClient

@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Create a test user via the register endpoint."""
    resp = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Test1234!",
    })
    assert resp.status_code == 201
    return resp.json()

@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, registered_user: dict) -> AsyncClient:
    """AsyncClient pre-authenticated as the registered test user."""
    resp = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "Test1234!",
    })
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

### Anti-Patterns to Avoid

- **Embedding mutable state (email, roles) in the JWT payload:** Query the DB on each request instead. Only store `sub` (user_id) and `exp`. [VERIFIED: PITFALLS.md Pitfall 12]
- **Using `auto_error=True` on HTTPBearer:** Returns 403 instead of 401 for missing tokens. Use `auto_error=False` and check for `None` manually. [VERIFIED: FastAPI GitHub Discussion #12384]
- **Fetching notes with `WHERE id = note_id` only:** Omits ownership — enables user A to read user B's data (PITFALLS.md Pitfall 13). Always fetch by ID then check ownership.
- **Running `alembic upgrade head` in-process at startup:** Race condition for multiple replicas. Keep the Phase 2 pattern: run Alembic as a pre-start step.
- **Accepting `user_id` from request body on note creation:** D-10 — always assign `user_id = current_user.id` server-side.
- **Returning 404 for cross-user access on existing notes:** D-08 explicitly chose 403 for teachable HTTP semantics. Do not change to 404-hiding.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom hash + salt logic | `pwdlib[argon2]` `PasswordHash.recommended()` | Argon2id tuning (memory, iterations, parallelism), timing-safe comparison — all handled correctly |
| JWT encode/decode | Custom base64 + HMAC | `PyJWT` `jwt.encode()` / `jwt.decode()` | Clock skew, `exp` leeway, `InvalidTokenError` hierarchy — all handled |
| Email validation | Regex patterns | Pydantic `EmailStr` (via `pydantic[email]`) | RFC 5322 compliance, MX record validation, DNS checks |
| Bearer token extraction | Manual `request.headers.get("Authorization")` | FastAPI `HTTPBearer` security scheme | Swagger UI "Authorize" button integration, standard error handling |
| `uuid4` for jti | Random string | `str(uuid.uuid4())` | 128-bit UUID4 is the JTI standard (RFC 7519 §4.1.7) |

**Key insight:** Security-sensitive operations have subtle failure modes. pwdlib and PyJWT handle constant-time comparison, timing attacks, and spec compliance correctly. Never hand-roll cryptography.

---

## Common Pitfalls

### Pitfall 1: NOT NULL FK Migration Order Failure

**What goes wrong:** Adding a NOT NULL `user_id` FK to `notes` without first emptying the table causes `ALTER TABLE ... MODIFY COLUMN ... NOT NULL` to fail: "Column 'user_id' cannot be null" for existing rows.

**Why it happens:** D-11 says TRUNCATE is acceptable, but the migration must TRUNCATE *before* adding the column — not after.

**How to avoid:** Migration sequence: (1) TRUNCATE notes, (2) add column nullable, (3) create FK constraint, (4) alter to NOT NULL. Since notes table is empty after TRUNCATE, step 4 succeeds immediately.

**Warning signs:** `op.add_column(..., nullable=False)` without a preceding TRUNCATE or UPDATE.

### Pitfall 2: Missing `users` Migration as Prerequisite

**What goes wrong:** The migration that adds `user_id` FK to `notes` runs before the `users` table exists → `op.create_foreign_key` fails with "Referenced table 'users' does not exist."

**Why it happens:** Alembic migrations are independent files; the dependency is declared via `down_revision`.

**How to avoid:** Migration YYYY (`add_user_id_to_notes`) must have `down_revision = "XXXX"` pointing to the `create_users_and_refresh_tokens` migration. Never add a FK to a nonexistent table.

### Pitfall 3: HTTPBearer Returns 403 Instead of 401

**What goes wrong:** With `HTTPBearer(auto_error=True)` (the default), a missing or malformed `Authorization` header returns **403 Forbidden** instead of **401 Unauthorized** in FastAPI 0.115.x.

**Why it happens:** FastAPI's internal HTTPBearer implementation raises `HTTPException(403)` when `auto_error=True` and credentials are absent.

**How to avoid:** Use `HTTPBearer(auto_error=False)`. In `get_current_user`, check `if credentials is None: raise HTTPException(401)`. This also enables clean 401s for expired tokens. [VERIFIED: FastAPI GitHub Discussion #12384]

### Pitfall 4: JWT Access Token Carrying User Email or Roles

**What goes wrong:** Access token payload includes `{"sub": "1", "email": "user@x.com", "role": "admin"}`. When email or role changes in DB, the token still carries the old value for up to 15 minutes.

**Why it happens:** Beginners put user attributes in JWT to avoid DB lookups per request. With a 15-min TTL this is low risk but creates subtle bugs.

**How to avoid:** Access token carries only `sub` (user_id as string) and `exp`. `get_current_user` does a DB lookup (single SELECT by PK — fast, indexed). No mutable state in token payload.

### Pitfall 5: Existing Note Tests Break After Auth is Added

**What goes wrong:** `test_notes_crud.py` and `test_notes_list.py` use the `client` fixture which hits unprotected endpoints. After Phase 3, all note endpoints require `Authorization: Bearer <token>` → existing tests return 401 instead of 200/201/204.

**Why it happens:** Note endpoints were unprotected in Phase 2. Phase 3 adds `Depends(get_current_user)` to all note routes.

**How to avoid:** Replace the `client` fixture with `auth_client` (pre-authenticated) in all existing note tests. This is expected upgrade work, not test breakage.

### Pitfall 6: `ForeignKey` Column Referencing `users.id` Before `User` Model is Imported

**What goes wrong:** Alembic autogenerate or SQLAlchemy engine init fails with `NoReferencedTableError: Foreign key associated with column 'notes.user_id' could not find table 'users'`.

**Why it happens:** SQLAlchemy resolves FK references at metadata level. If `User` model is not imported before `Note` model metadata is accessed, the `users` table doesn't exist in metadata.

**How to avoid:** In `alembic/env.py`, import ALL models (from `app.auth.models import User, RefreshToken` AND `from app.notes.models import Note`) before `target_metadata = Base.metadata`. This ensures all tables are registered.

### Pitfall 7: Pydantic EmailStr Requires `email-validator` Extra

**What goes wrong:** Using `from pydantic import EmailStr` without installing `email-validator` raises `ImportError: email-validator is not installed, run 'pip install pydantic[email]'` at startup.

**Why it happens:** `EmailStr` is a Pydantic v2 type that requires an optional dependency.

**How to avoid:** `uv add "pydantic[email]"` — this installs `email-validator`. Verify the import works in the registration schema before wiring the router.

### Pitfall 8: Leaking DB `depends_on` Override in Tests

**What goes wrong:** A test creates an `auth_client` fixture with `app.dependency_overrides[get_current_user] = lambda: fake_user`. If `dependency_overrides.clear()` is not called at teardown, subsequent tests inherit the override and always see `fake_user`.

**Why it happens:** FastAPI's `dependency_overrides` is a module-level dict on the `app` object. It persists across tests unless cleared.

**How to avoid:** Follow the Phase 2 pattern in `conftest.py`: always `app.dependency_overrides.clear()` at the end of the `client` fixture (already done). For additional overrides added in test-specific fixtures, use `try/finally` or an autouse `cleanup` fixture.

---

## Code Examples

### Registration Endpoint Shape

```python
# Source: CONTEXT.md D-12, D-13, D-14 + FastAPI official OAuth2 tutorial [CITED: fastapi.tiangolo.com/tutorial/security/oauth2-jwt/]
from pydantic import BaseModel, EmailStr, field_validator
import re

class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one symbol")
        return v

class UserRead(BaseModel):
    id: int
    email: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

### Pydantic Settings Extension

```python
# Source: pydantic-settings docs + CONTEXT.md [CITED: docs.pydantic.dev/latest/concepts/pydantic_settings/]
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "..."

    # JWT (Phase 3) — already in .env.example
    jwt_secret_key: str = "changeme-jwt-secret-key-minimum-32-bytes-long"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
```

### Cross-User Isolation Test Structure

```python
# [ASSUMED] — pattern derived from Phase 2 conftest.py + CONTEXT.md success criteria
async def test_cross_user_note_returns_403(client: AsyncClient, ...) -> None:
    """User A cannot read User B's note — returns 403 (D-08)."""
    # Create user_a + user_b, each authenticated
    # User A creates a note
    note_resp = await user_a_client.post("/notes/", json={"content": "A's secret"})
    note_id = note_resp.json()["id"]

    # User B tries to read it
    resp = await user_b_client.get(f"/notes/{note_id}")
    assert resp.status_code == 403

async def test_list_notes_isolates_per_user(client: AsyncClient, ...) -> None:
    """GET /notes/ returns only the authenticated user's notes (D-09)."""
    await user_a_client.post("/notes/", json={"content": "A's note"})
    await user_b_client.post("/notes/", json={"content": "B's note"})

    resp = await user_a_client.get("/notes/")
    items = resp.json()["items"]
    assert all(item["content"] != "B's note" for item in items)
    assert len(items) == 1
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `passlib` for password hashing | `pwdlib[argon2]` | FastAPI-Users v13 (2024) | passlib broken on Python 3.13+; pwdlib is the stack-locked replacement |
| `python-jose` for JWT | `PyJWT` (`import jwt`) | FastAPI official tutorial updated (2024) | python-jose is abandoned; PyJWT is the official FastAPI recommendation |
| OAuth2PasswordRequestForm (form body) | JSON body login | CONTEXT.md D (discretion) | JSON body is API-first default; form body only needed for Swagger "Try it out" OAuth2 flow |
| HTTPBearer `auto_error=True` | `auto_error=False` + manual 401 | FastAPI 0.115.x behavior | Returns 403 not 401 by default; `auto_error=False` gives correct 401 |
| `jwt.encode()` returning bytes (PyJWT < 2.0) | Returns `str` in PyJWT 2.x | PyJWT 2.0 (2021) | No `.decode("utf-8")` call needed; just use the returned string directly |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Package legitimacy (PyJWT, pwdlib, email-validator) not run through slopcheck — marked OK based on download stats + official docs | Package Legitimacy Audit | Low: these are well-established packages with massive download counts and official references |
| A2 | Auth test fixtures (registered_user, auth_client) structure | Code Examples / Pattern 8 | Low: pattern follows Phase 2 conftest.py design; may need adjustment to exact fixture scope |
| A3 | Cross-user isolation test structure | Code Examples | Low: exact test parameter names depend on final conftest fixtures |
| A4 | `INTEGER(unsigned=True)` is the correct import path for user_id on Note (vs `BIGINT(unsigned=True)`) | Pattern 5 | Low: consistent with existing notes.id definition (also INTEGER unsigned) |

---

## Open Questions

1. **`updated_at` on `users` table**
   - What we know: CONTEXT.md says it is "optional" (Claude's discretion)
   - What's unclear: Whether to include it for symmetry with the notes model
   - Recommendation: Include `updated_at` for consistency; the overhead is negligible and it will be useful if password changes are added later

2. **Session token approach: `session` fixture reuse in auth tests**
   - What we know: The Phase 2 `session` fixture uses transaction-rollback isolation. Auth tests that create users + tokens will also need this isolation.
   - What's unclear: Whether to create separate fixtures for `user_a_session` + `user_a_client` or share the existing `session` fixture
   - Recommendation: Add `registered_user` and `auth_client` fixtures to `conftest.py` (function-scoped, reuse the existing `session` and `client` fixtures) rather than creating new DB connections

3. **`NoteCreate` schema `user_id` field exclusion**
   - What we know: D-10 says `user_id` is never accepted from client body
   - What's unclear: Whether `NoteCreate` schema should omit `user_id` entirely (safer) or include it but ignore it
   - Recommendation: Omit `user_id` from `NoteCreate` entirely; the service method signature becomes `create(data: NoteCreate, user_id: int)`

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Desktop | testcontainers MySQL | ✓ | 29.4.2 | — |
| uv | Package management | ✓ | 0.11.24 | — |
| Alembic | DB migrations | ✓ | 1.18.4 (in venv) | — |
| pytest | Test runner | ✓ | 9.1.1 (in venv) | — |
| MySQL 8.4 (testcontainers) | Integration tests | ✓ (via Docker) | mysql:8.4 | — |

**Missing dependencies with no fallback:** None.

**Note:** Docker Desktop daemon was not running at research time (testcontainers tests would fail). This is expected in the CI/CD context; Docker must be running when executing `uv run pytest`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 0.24.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` already set |
| Quick run command | `uv run pytest tests/test_auth.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | POST /auth/register → 201, duplicate → 409, weak password → 422 | integration | `uv run pytest tests/test_auth.py::test_register_* -x` | ❌ Wave 0 |
| AUTH-01 | Malformed email → 422 | integration | `uv run pytest tests/test_auth.py::test_register_invalid_email -x` | ❌ Wave 0 |
| AUTH-02 | POST /auth/login → 200 with access_token + refresh_token | integration | `uv run pytest tests/test_auth.py::test_login_returns_tokens -x` | ❌ Wave 0 |
| AUTH-02 | Wrong password → 401 | integration | `uv run pytest tests/test_auth.py::test_login_wrong_password -x` | ❌ Wave 0 |
| AUTH-03 | POST /auth/refresh → new access token, old refresh jti revoked | integration | `uv run pytest tests/test_auth.py::test_refresh_rotation -x` | ❌ Wave 0 |
| AUTH-03 | POST /auth/logout → 204; subsequent refresh → 401 | integration | `uv run pytest tests/test_auth.py::test_logout_revokes_token -x` | ❌ Wave 0 |
| AUTH-03 | Expired access token → 401 on protected endpoint | integration | `uv run pytest tests/test_auth.py::test_expired_token_returns_401 -x` | ❌ Wave 0 |
| AUTH-04 | GET /notes/{id} with user B's token → 403 | integration | `uv run pytest tests/test_notes_isolation.py::test_cross_user_get_returns_403 -x` | ❌ Wave 0 |
| AUTH-04 | GET /notes/ returns only current user's notes | integration | `uv run pytest tests/test_notes_isolation.py::test_list_isolation -x` | ❌ Wave 0 |
| AUTH-04 | GET /notes/{nonexistent_id} → 404 | integration | `uv run pytest tests/test_notes_isolation.py::test_missing_note_returns_404 -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth.py -x` (auth tests only, ~30s)
- **Per wave merge:** `uv run pytest tests/ -x` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth.py` — covers AUTH-01, AUTH-02, AUTH-03 (register/login/refresh/logout/401)
- [ ] `tests/test_notes_isolation.py` — covers AUTH-04 (cross-user 403/404, list isolation)
- [ ] `tests/conftest.py` additions — `registered_user`, `auth_client`, `user_a_client`, `user_b_client` fixtures

*(Existing `test_notes_crud.py` and `test_notes_list.py` must be updated to use `auth_client` instead of `client` once note endpoints are protected.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | pwdlib[argon2] (Argon2id) + Pydantic password complexity validator |
| V3 Session Management | yes | 15-min access JWT + 7-day rotating refresh token with DB-backed revocation |
| V4 Access Control | yes | `get_current_user` dependency on all note routes + `WHERE user_id = current_user.id` in all queries |
| V5 Input Validation | yes | Pydantic EmailStr + @field_validator (password) + FastAPI 422 auto-validation |
| V6 Cryptography | yes | HS256 + 32-byte random secret key; Argon2id for passwords — never hand-rolled |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JWT replay after logout | Repudiation | jti stored in `refresh_tokens` table; `POST /auth/logout` marks jti revoked |
| Brute-force login | Elevation of Privilege | Out of scope (D deferred) — Argon2id makes brute force slow; rate limiting deferred to later phase |
| Cross-user data access | Information Disclosure | `WHERE user_id = current_user.id` on all note list queries; ownership check (403) on single-note endpoints |
| Weak password | Elevation of Privilege | Pydantic @field_validator enforces length + composition at schema layer → 422 |
| JWT secret in code / image | Information Disclosure | `JWT_SECRET_KEY` via `.env` (gitignored) + pydantic-settings; never baked into Dockerfile |
| Stale JWT after user deletion | Elevation of Privilege | `get_current_user` does a DB lookup → 401 if user row deleted (sub not found) |
| Missing Authorization header | Spoofing | HTTPBearer `auto_error=False` + manual 401 check in `get_current_user` |
| Timing attack on password verify | Information Disclosure | pwdlib Argon2id uses constant-time comparison internally |

### ASVS Level Target
This phase targets **ASVS Level 1** (baseline) with selected Level 2 controls:
- Refresh token rotation (Level 2 practice, D-04) — already in scope
- DB-backed revocation via jti (Level 2) — already in scope
- Cascade revocation on reuse detection (Level 2) — **deferred to later phase per D-06**

---

## Sources

### Primary (HIGH confidence)
- PyJWT official docs — `pyjwt.readthedocs.io/en/stable/usage.html` — jti claim, exp claim, exception hierarchy
- FastAPI official security tutorial — `fastapi.tiangolo.com/tutorial/security/oauth2-jwt/` — OAuth2PasswordBearer, get_current_user, pwdlib patterns
- FastAPI official security reference — `fastapi.tiangolo.com/reference/security/` — HTTPBearer, HTTPAuthorizationCredentials
- pwdlib official docs — `frankie567.github.io/pwdlib/` — PasswordHash.recommended(), hash(), verify()
- SQLAlchemy 2.0 official docs — `docs.sqlalchemy.org/en/20/orm/basic_relationships.html` — Many-to-one FK pattern, Mapped types
- Alembic official docs — `alembic.sqlalchemy.org/en/latest/ops.html` — op.add_column, op.create_foreign_key, NOT NULL migration sequence
- Existing project codebase — `app/notes/`, `tests/conftest.py`, `pyproject.toml` — direct inspection of Phase 2 patterns

### Secondary (MEDIUM confidence)
- PyPI registry API — `pypi.org/pypi/{package}/json` — verified current versions (PyJWT 2.13.0, pwdlib 0.3.0, email-validator 2.3.0)
- pypistats.org — download statistics for legitimacy verification
- FastAPI GitHub Discussion #12384 — HTTPBearer returns 403 not 401 with auto_error=True; fix is auto_error=False
- CONTEXT.md decisions D-01 through D-14 — all implementation decisions locked

### Tertiary (LOW confidence / ASSUMED)
- WebSearch: refresh token rotation patterns — cross-user test fixture structure inferred from community examples
- OWASP ASVS v4 requirements — summary from web search; full text not fetched

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified on PyPI; API patterns verified in official FastAPI + PyJWT + SQLAlchemy docs
- Architecture: HIGH — directly mirrors the Phase 2 codebase structure, which is already established
- Migration strategy: HIGH — Alembic op sequence verified against official docs; D-11 makes the TRUNCATE approach unambiguous
- Pitfalls: HIGH — most are verified against official docs or GitHub issues; auth-specific pitfalls drawn from PITFALLS.md + new research
- Test patterns: MEDIUM — test structure inferred from Phase 2 conftest.py + community patterns

**Research date:** 2026-06-25
**Valid until:** 2026-08-25 (stable ecosystem — PyJWT and pwdlib are slow-moving libraries)
