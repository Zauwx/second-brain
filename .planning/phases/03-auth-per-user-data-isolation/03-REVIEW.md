---
phase: 03-auth-per-user-data-isolation
reviewed: 2026-06-25T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - alembic/env.py
  - alembic/versions/0002_create_users_and_refresh_tokens.py
  - alembic/versions/0003_add_user_id_to_notes.py
  - app/auth/__init__.py
  - app/auth/models.py
  - app/auth/repository.py
  - app/auth/router.py
  - app/auth/schemas.py
  - app/auth/service.py
  - app/core/config.py
  - app/core/dependencies.py
  - app/main.py
  - app/notes/models.py
  - app/notes/repository.py
  - app/notes/router.py
  - app/notes/schemas.py
  - app/notes/service.py
  - tests/conftest.py
  - tests/test_auth.py
  - tests/test_notes_crud.py
  - tests/test_notes_isolation.py
  - tests/test_notes_list.py
  - tests/test_notes_service_isolation.py
findings:
  critical: 2
  warning: 7
  info: 5
  total: 14
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-25
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Reviewed the JWT auth + per-user data isolation phase. The core isolation model is sound:
ownership is enforced in `NoteService.get_or_404_owned` (404-then-403), list/count queries are
owner-scoped in `NoteRepository.list_paginated`, `user_id` is assigned server-side and is absent
from `NoteCreate`, JWT signature/expiry are verified on every request, `get_current_user` does a
fresh DB lookup, and refresh-token rotation revokes the old jti while leaving siblings valid. The
`.env` file is gitignored and untracked, and the sort whitelist prevents ORM-column injection.

However, two Critical defects exist for a security-sensitive phase: (1) the application will run
with a hardcoded, publicly-known default JWT signing secret if `JWT_SECRET_KEY` is unset — there
is no production guard, so anyone can forge tokens for any user; (2) a non-numeric `sub` claim
raises an unhandled `ValueError` (500) instead of 401, in both `get_current_user` and the refresh
flow. Several Warnings concern non-atomic token rotation, an unverified stored `expires_at`, and
an unused unscoped `get_or_404` that is a footgun for future endpoints.

## Structural Findings (fallow)

No `<structural_findings>` block was provided with this review. This section is intentionally empty.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Application falls back to a hardcoded, publicly-known JWT signing secret

**File:** `app/core/config.py:25`
**Issue:** `jwt_secret_key` defaults to the literal string
`"changeme-jwt-secret-key-minimum-32-bytes-long"`. Because `Settings` silently uses this default
when `JWT_SECRET_KEY` is not set in the environment, a misconfigured production deployment will
sign and verify all access/refresh tokens with a secret that is committed to the repository and
published in `.env.example:44`. Anyone can mint a token like
`jwt.encode({"sub": "1", "exp": ...}, "changeme-jwt-secret-key-minimum-32-bytes-long", "HS256")`
and impersonate any user, completely defeating the auth + isolation goal of this phase. The same
applies to `database_url` containing `changeme-password`. There is no startup assertion that the
secret was overridden outside `development`.
**Fix:** Fail closed when running outside development with a default/weak secret. For example, add
a validator to `Settings`:
```python
from pydantic import model_validator

_INSECURE_DEFAULT = "changeme-jwt-secret-key-minimum-32-bytes-long"

@model_validator(mode="after")
def _require_secret_in_prod(self) -> "Settings":
    if self.environment != "development":
        if self.jwt_secret_key == _INSECURE_DEFAULT or len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be overridden with a 32+ byte random secret in non-dev environments"
            )
    return self
```
Consider making `jwt_secret_key` have no default at all so the app refuses to boot without it.

### CR-02: Non-numeric `sub` claim raises 500 instead of 401 (auth crash / improper error path)

**File:** `app/core/dependencies.py:99` (also `app/auth/service.py:187`)
**Issue:** After extracting `sub`, the code calls `int(user_id_str)` with no error handling. A
token whose signature is valid for this secret but whose `sub` is non-numeric (e.g. an email, a
UUID, or `"null"`) raises `ValueError: invalid literal for int()`. This is an unhandled exception
inside the dependency, producing a 500 response instead of the documented 401. The docstring and
tests (`test_token_for_deleted_user_returns_401`) assume any bad token yields 401; a non-integer
`sub` breaks that contract. The same unguarded `int(user_id_str)` appears in
`rotate_refresh_token` at `service.py:187`, where it would surface as a 500 on `/auth/refresh`.
A future token-issuing change (e.g. switching `sub` to email) would silently turn every
authenticated request into a 500.
**Fix:** Guard the cast and map failure to the existing 401 path:
```python
try:
    user_id = int(user_id_str)
except (TypeError, ValueError) as exc:
    raise credentials_exception from exc
user = await AuthRepository(db).get_user_by_id(user_id)
```
Apply the equivalent guard in `rotate_refresh_token` before `int(user_id_str)`.

## Warnings

### WR-01: Refresh-token rotation is not atomic — crash between revoke and insert loses the chain

**File:** `app/auth/service.py:185-201`
**Issue:** `rotate_refresh_token` calls `revoke_refresh_token(token_record)` (which `commit()`s)
and then separately `create_refresh_token(...)` (a second `commit()`). These are two independent
transactions. If the process crashes, the DB connection drops, or `create_refresh_token` raises
(e.g. an extremely unlikely jti UUID collision on the UNIQUE index) after the revoke commit, the
old token is already revoked but no new token exists — the user is silently logged out with no
recovery path. The same two-commit pattern in `login` is less severe (no prior revoke), but
rotation specifically should be one transaction.
**Fix:** Perform the revoke and the new-token insert in a single transaction. Mutate
`token_record` and `session.add(new_token)` without an intermediate commit, then commit once at
the end of the service method. This requires the repository methods to flush rather than commit,
with the service owning the transaction boundary.

### WR-02: Stored `refresh_tokens.expires_at` is written but never enforced

**File:** `app/auth/service.py:176-182`, `app/auth/repository.py:74-79`
**Issue:** `rotate_refresh_token` looks up the token by jti and checks only
`token_record.revoked`. It never compares `token_record.expires_at` to now. Expiry is currently
enforced solely by `jwt.decode` raising `ExpiredSignatureError`. That works as long as the JWT
`exp` and the stored `expires_at` always agree, but the stored column is dead defense-in-depth: a
token with a tampered/long `exp` that still verifies, or any future drift between the two values,
would not be caught by the DB layer the column exists to back. For a security phase this is a
latent gap — the persisted expiry gives a false sense of a second check that is not actually run.
**Fix:** After fetching `token_record`, also reject expired rows:
```python
now = datetime.now(UTC).replace(tzinfo=None)
if token_record is None or token_record.revoked or token_record.expires_at <= now:
    raise HTTPException(401, "Refresh token revoked or not found", ...)
```

### WR-03: Unused, unscoped `get_or_404` is a data-isolation footgun

**File:** `app/notes/service.py:44-56`
**Issue:** `get_or_404` fetches a note by id with no ownership check and is documented "Kept for
internal use only." It is not referenced anywhere in the reviewed code (all endpoints use
`get_or_404_owned`). Leaving an unscoped accessor in the service surface invites a future
contributor to wire it into a new endpoint, silently reintroducing the cross-user read that this
entire phase exists to prevent. Dead code that bypasses the central security control is worse than
ordinary dead code.
**Fix:** Remove `get_or_404` entirely, or if a future internal caller genuinely needs an
owner-agnostic fetch, rename it to something explicit (e.g. `_get_by_id_unchecked`) and keep it
private. Do not leave a public-looking, ownership-free getter on the service.

### WR-04: Login `verify` short-circuits on unknown email — timing side channel despite the comment

**File:** `app/auth/service.py:107-114`
**Issue:** The comment claims "always call verify even on None user to prevent timing attacks,"
but the code is `if user is None or not password_hash.verify(...)`. Python short-circuits `or`, so
when `user is None` the Argon2id `verify` is never called. Unknown-email requests therefore return
markedly faster than wrong-password requests (which pay the full Argon2id cost), giving an
attacker a timing oracle for user enumeration — exactly what the comment says it prevents.
**Fix:** Verify against a fixed dummy hash when the user is missing so both paths perform one
Argon2id verification:
```python
_DUMMY_HASH = password_hash.hash("timing-equalizer")
...
if user is None:
    password_hash.verify(data.password, _DUMMY_HASH)  # constant-time decoy
    raise HTTPException(401, "Invalid credentials", ...)
if not password_hash.verify(data.password, user.hashed_password):
    raise HTTPException(401, "Invalid credentials", ...)
```

### WR-05: `revoke_refresh_token` is not idempotent under concurrent rotation (replay race window)

**File:** `app/auth/service.py:176-185`
**Issue:** The revoked-check (`token_record.revoked`) and the revoke (`revoke_refresh_token`) are
read-then-write with no locking. Two concurrent `/auth/refresh` calls presenting the same valid
refresh token can both pass the `revoked is False` check before either commits the revoke, so both
succeed and two new token chains are issued from one token — a refresh-token replay that the D-06
"revoked jti → 401" rule is meant to stop. The single-client tests do not exercise concurrency, so
this passes the suite while remaining exploitable.
**Fix:** Make revocation conditional in SQL (`UPDATE ... SET revoked=1 WHERE jti=:jti AND
revoked=0`) and treat `rowcount == 0` as "already revoked → 401". Alternatively `SELECT ... FOR
UPDATE` the row inside the rotation transaction.

### WR-06: `NoteUpdate` cannot clear `title`/`source_url` despite docstrings claiming it can

**File:** `app/notes/schemas.py:44-58`, `app/notes/repository.py:129-131`
**Issue:** `NoteUpdate.title` and `source_url` are documented "set to null to clear," but
`repository.update` uses `data.model_dump(exclude_unset=True)`. Pydantic cannot distinguish
"field omitted" from "field explicitly set to null" here in a way that lets a client clear a
column: if the client sends `{"title": null}` it is included (good), but the broader pattern means
the only signal is presence. More concretely, there is no test asserting a null clear actually
nulls the column, and the partial-update loop will happily set `content = None` if a client sends
`{"content": null}` is blocked by `min_length=1`, but `title`/`source_url` nulling is untested.
The documented "clear to null" behavior is unverified and may not work as advertised.
**Fix:** Add an explicit test that `PUT {"title": null}` results in `title is None` in the
response, and confirm `exclude_unset` vs `exclude_none` semantics match the documented contract.
If clearing is intended, ensure `model_dump(exclude_unset=True)` includes explicitly-null fields
(it does) and the repository assigns them — then lock the behavior with a regression test.

### WR-07: `logout` decode failure returns 401, contradicting idempotent-logout intent

**File:** `app/auth/service.py:221-233`, `app/auth/router.py:106-124`
**Issue:** `logout` is documented as idempotent ("If the token is already revoked or not found,
the call is a no-op"). But an undecodable/expired token raises 401 rather than returning 204.
A client that already logged out (token now expired) and retries logout gets a 401, not the
idempotent 204 the docstring implies. This is an inconsistent contract: a revoked-but-valid JWT
returns 204 (no-op), while an expired JWT returns 401, for semantically the same "I want this
session gone" intent. The test `test_logout_returns_204` only covers the fresh-token path.
**Fix:** Decide the contract explicitly. If logout is meant to be idempotent and side-effect-only,
return 204 even on an undecodable token (you cannot revoke what you cannot parse, but the session
is effectively dead anyway). Document and test whichever behavior is chosen so it is not
accidentally inconsistent with refresh.

## Info

### IN-01: `TRUNCATE TABLE notes` in migration 0003 is irreversible and unguarded

**File:** `alembic/versions/0003_add_user_id_to_notes.py:36`
**Issue:** The upgrade unconditionally `TRUNCATE`s all notes. This is documented as a dev-only data
reset (D-11), and `downgrade()` correctly cannot restore the data. The risk is that if this
migration is ever applied to a populated environment it silently destroys all notes with no
backfill and no confirmation. For a learning project this is acceptable, but it is a permanent,
unrecoverable data-loss step embedded in version control.
**Fix:** At minimum, add a loud comment/guard noting this migration must never run against data you
care about; ideally gate destructive behavior behind an explicit env flag or refuse to run when
`SELECT COUNT(*) FROM notes > 0` without an override.

### IN-02: `revoked` server_default mismatch between migration and ORM model

**File:** `alembic/versions/0002_create_users_and_refresh_tokens.py:91` vs `app/auth/models.py:102`
**Issue:** The migration sets a DB-level `server_default=sa.text("0")` for `refresh_tokens.revoked`,
while the ORM model declares `default=False` (a Python-side default, no `server_default`). They
happen to agree, but the divergence means an `alembic revision --autogenerate` could emit a
spurious diff, and a raw `INSERT` outside the ORM relies on the migration default while ORM inserts
rely on the Python default. Align them to avoid autogenerate churn.
**Fix:** Add `server_default=text("0")` to the model column (or drop the Python `default` and rely
on the server default) so the model and migration describe the same column.

### IN-03: Pagination/JWT magic numbers and dead alias

**File:** `app/core/config.py:27-28`, `app/notes/schemas.py:90`
**Issue:** `access_token_expire_minutes=15` and `refresh_token_expire_days=7` are reasonable but
undocumented inline; `PaginatedNotes = NoteListResponse` at schemas.py:90 is a "deprecated alias
kept for backward compatibility" with no remaining references in the reviewed code — dead code.
**Fix:** Remove the unused `PaginatedNotes` alias if nothing imports it. (Low priority.)

### IN-04: `get_current_user` does not assert token `type` (access vs refresh)

**File:** `app/core/dependencies.py:83-96`
**Issue:** Access and refresh tokens are both signed with the same secret and algorithm; the only
structural difference is that refresh tokens carry a `jti` and longer `exp`. `get_current_user`
accepts any validly-signed token with a numeric `sub`, so a refresh token presented as a Bearer
access token would authenticate API calls until its (much longer) expiry. This widens the blast
radius of a leaked refresh token. Not exploitable for privilege escalation (still the same user),
but it conflates the two token classes.
**Fix:** Add a `"type": "access"` / `"type": "refresh"` claim at issuance and assert
`payload.get("type") == "access"` in `get_current_user` (and `"refresh"` in the refresh/logout
paths). Reject mismatches with 401.

### IN-05: Comment in repository overstates SQL-injection safety reasoning

**File:** `app/notes/repository.py:107-110`
**Issue:** The filter uses `Note.content.ilike(f"%{filter}%")`, which is safe because SQLAlchemy
binds `%{filter}%` as a single bound parameter — correct. However the inline comment ("the f-string
only adds wildcards around an already-escaped bound value") is slightly misleading: the value is
parameter-bound, not "escaped," and LIKE metacharacters (`%`, `_`) inside the user's filter are NOT
escaped, so a filter of `%` matches everything and `_` is a wildcard. This is a correctness/UX
nuance, not an injection issue.
**Fix:** If literal substring matching is intended, escape `%` and `_` in the user input before
interpolation and use `.ilike(..., escape="\\")`. At minimum, fix the comment to say "parameter-
bound" rather than "escaped."

---

_Reviewed: 2026-06-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
