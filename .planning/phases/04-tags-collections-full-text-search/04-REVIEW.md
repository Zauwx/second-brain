---
phase: 04-tags-collections-full-text-search
reviewed: 2026-06-30T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - alembic/versions/0004_add_tags.py
  - alembic/versions/0005_add_collections.py
  - app/collections/__init__.py
  - app/collections/models.py
  - app/collections/repository.py
  - app/collections/router.py
  - app/collections/schemas.py
  - app/collections/service.py
  - app/core/dependencies.py
  - app/main.py
  - app/notes/models.py
  - app/notes/repository.py
  - app/notes/router.py
  - app/notes/schemas.py
  - app/notes/service.py
  - app/search/__init__.py
  - app/search/repository.py
  - app/search/router.py
  - app/search/schemas.py
  - app/search/service.py
  - app/tags/__init__.py
  - app/tags/models.py
  - app/tags/repository.py
  - app/tags/router.py
  - app/tags/schemas.py
  - app/tags/service.py
  - docker-compose.yml
  - tests/conftest.py
  - tests/test_collections.py
  - tests/test_notes_tag_filter.py
  - tests/test_phase4_isolation.py
  - tests/test_search.py
  - tests/test_tags.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-30T00:00:00Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the tags, collections, and full-text-search vertical slices plus the supporting
note/model/dependency changes. Per-user isolation is implemented consistently in the
service layer (404-then-403 ownership contract), and the FULLTEXT search path correctly
binds the query as a parameter via `match(..., against=q)` — no SQL injection risk there.

However, the review surfaced one **BLOCKER**: the entire tag attach/detach feature never
commits its writes, so tagging is silently discarded in production. This is masked by the
test fixtures (single rolled-back transaction, read-back in the same session), so the green
test suite gives a false sense of correctness. Additional warnings cover an incomplete
BOOLEAN-MODE sanitizer that can still 500, a NOT-NULL clearing path that 500s, and
isolation tests that do not actually prove isolation.

## Critical Issues

### CR-01: Tag attach/detach never commit — tag changes are silently lost in production

**File:** `app/tags/repository.py:55-65, 83-100` (and `app/tags/service.py:64-87`)

**Issue:** The session factory is configured with `autocommit=False`
(`app/database.py:50-55`) and the request dependency `get_db`
(`app/core/dependencies.py:50-53`) only does `async with AsyncSessionLocal() as session: yield session`
— it never commits on teardown; closing the session rolls back the open transaction.

Every other write path commits explicitly inside the repository
(`NoteRepository.create/update/delete` and `CollectionRepository.create/add_note/remove_note`
all call `await self._session.commit()`). The tag write path does **not**:

- `TagRepository.find_or_create` uses `begin_nested()` (a SAVEPOINT) and then returns — no outer `commit()`.
- `TagRepository.attach` / `detach` call only `await self._session.flush()` — no `commit()`.
- `TagService.attach_tag` / `detach_tag` add no commit either.

Result: `POST /notes/{id}/tags` returns `200` with the tag in the response body (the object
is read back from the in-memory session before close), but when the request finishes and the
session closes, the INSERT into `tags`, the `note_tags` join row, and the detach are all
**rolled back**. The new tag, the attachment, and detachments are never persisted. A
subsequent `GET /notes/{id}` in a fresh request/session shows no tag.

This is invisible in the test suite because the `session` fixture
(`tests/conftest.py:81-94`) wraps the whole test in one outer transaction and the test reads
back within that same session before the test-level rollback — so `flush()` is sufficient for
the assertion to pass, masking the missing `commit()`.

**Fix:** Commit in the tag write path, matching the rest of the repositories. Either commit in
the repository methods, or once in the service after the mutation:

```python
# app/tags/repository.py
async def attach(self, note: Note, tag: Tag) -> None:
    if tag not in note.tags:
        note.tags.append(tag)
    await self._session.commit()   # was: flush()

async def detach(self, note: Note, tag: Tag) -> None:
    note.tags.remove(tag)
    await self._session.commit()   # was: flush()
```

`find_or_create` must also persist the new tag (commit after the savepoint succeeds, or rely
on the subsequent `attach` commit — but verify the savepoint-created row survives the outer
commit). Add a multi-request integration test (e.g. attach via one committed session, then
re-read via a *new* session) so this regression cannot reappear.

## Warnings

### WR-01: BOOLEAN-MODE sanitizer is incomplete — several operators still produce a 500

**File:** `app/search/service.py:13-42`

**Issue:** `sanitize_boolean_query` strips `@`, runs of `+`/`-`, and trailing `+`/`-`, and the
docstring/router claim "Malformed operator sequences ... are sanitized — never return 500."
But MySQL BOOLEAN MODE has more special characters than `+ - @`: `"` (phrase), `(` `)`
(grouping), `~` (rank negation), `<` `>` (contribution), and a lone `*`. None of these are
sanitized. An unbalanced phrase quote or paren raises an InnoDB syntax error that propagates
unhandled to a `500`:

- `GET /search/?q="` → unterminated phrase → syntax error → 500
- `GET /search/?q=(` or `q=)` → unbalanced grouping → syntax error → 500

The existing tests only cover `@`, `++`, and whitespace, so the gap is not caught.

**Fix:** Either whitelist allowed characters (alphanumerics, whitespace, and the supported
operators only) or strip/balance `" ( ) ~ < >` and leading `*`. Add tests for `q='"'`,
`q='('`, `q=')'`. Alternatively, wrap the repository call in a try/except that converts an
InnoDB parse error to an empty `NoteListResponse`.

### WR-02: PUT /notes/{id} with `{"content": null}` clears a NOT NULL column → 500

**File:** `app/notes/schemas.py:51-55`, `app/notes/repository.py:165-182`

**Issue:** `NoteUpdate.content` is `str | None` with `min_length=1`. A client sending
`{"content": null}` passes validation (None is allowed; the length constraint only applies to
strings). `update()` uses `model_dump(exclude_unset=True)`, which *includes* an explicitly-sent
`null`, so `setattr(note, "content", None)` runs and `commit()` hits the `content` NOT NULL
constraint → `IntegrityError` → unhandled `500`. (Unlike `title`/`source_url`, content cannot
be cleared.)

**Fix:** Forbid clearing content — validate that if `content` is present it is a non-empty
string, or reject explicit null:

```python
content: str | None = Field(default=None, min_length=1)

@field_validator("content")
@classmethod
def _content_not_null(cls, v: str | None) -> str | None:
    if v is None:
        raise ValueError("content cannot be set to null")
    return v
```

Or filter out a `None` content in `update()` before `setattr`.

### WR-03: Search isolation tests do not actually prove isolation

**File:** `tests/test_search.py:87-103`, `tests/test_phase4_isolation.py:201-231`

**Issue:** Both "search does not leak across users" tests use `user_a_client`/`user_b_client`,
which run on the rollback `session` fixture (never committed). InnoDB FULLTEXT only indexes
committed rows, so user A's note is never indexed and `total == 0` is returned **regardless of
the `WHERE Note.user_id == user_id` clause**. The phase4 test even documents this. These tests
would still pass if the user-scoping filter in `SearchRepository.search_fulltext` were deleted
— so the headline isolation guarantee for search is unverified.

**Fix:** Write the search-isolation test against committed data (use the `ft_*` committed-session
fixture style with two distinct committed users) so the assertion genuinely exercises the
`Note.user_id` scoping. The repository code itself is correct; the test is the defect.

### WR-04: Alembic 0004 unconditionally DROPs the FULLTEXT index

**File:** `alembic/versions/0004_add_tags.py:72-73, 78-79`

**Issue:** `upgrade()` runs `ALTER TABLE notes DROP INDEX ft_notes_content` with no existence
guard, relying on the comment's assumption that an earlier revision (`d51191e92276`) created it.
If that index was never created, renamed, or already dropped on a given database, the migration
fails hard mid-upgrade. Same risk in `downgrade()`.

**Fix:** Make the DROP conditional, e.g. check
`information_schema.STATISTICS` for `ft_notes_content` before dropping, or use
`DROP INDEX IF EXISTS` semantics via a guarded `op.execute`. At minimum, assert the assumption
holds for all migration chains that reach 0004.

## Info

### IN-01: Misleading comment header on the association-table block

**File:** `app/notes/models.py:38-44`

**Issue:** The comment block titled "Association table: note_tags (many-to-many: Note ↔ Tag)"
is immediately followed by the definition of `note_collections` (the `note_tags` table is
defined below it). The header describes the wrong table.

**Fix:** Retitle the block to cover both association tables, or move the comment to sit directly
above `note_tags`.

### IN-02: Duplicate `get_db` definitions

**File:** `app/database.py:58-67` and `app/core/dependencies.py:50-53`

**Issue:** Two near-identical `get_db` async generators exist. Routers import the one from
`app.core.dependencies`; the one in `app.database` appears unused by the app. Divergent copies
invite drift (and both share the missing-commit behavior noted in CR-01).

**Fix:** Keep a single canonical `get_db` and import it everywhere, or document why two exist.

### IN-03: Deprecated alias `PaginatedNotes` retained

**File:** `app/notes/schemas.py:92-93`

**Issue:** `PaginatedNotes = NoteListResponse` is kept "for backward compatibility during
transition." If nothing imports it, it is dead code.

**Fix:** Grep for usages; if none remain, remove the alias.

---

_Reviewed: 2026-06-30T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
