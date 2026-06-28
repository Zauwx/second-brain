# Phase 4: Tags, Collections, Full-Text Search - Context

**Gathered:** 2026-06-28
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **organization + keyword-search layer** on top of the existing Note CRUD API — completing the full table-stakes REST surface before AI features begin (Phases 5–6).

In scope:
- **Tags (many-to-many)** — a `tags` table + a `note_tags` join table; attach/detach tags to notes (ORG-01)
- **Tag filtering** on the existing list endpoint — `GET /notes?tag=python` (single) and `?tag=python&tag=docker` (multiple), using `selectinload` to avoid N+1 (ORG-02)
- **Collections (many-to-many)** — a `collections` table + a `note_collections` join table; create collections, add/remove notes, and list a collection's notes via `GET /collections/{id}/notes` (ORG-03, ORG-04)
- **Full-text search** — a standalone `GET /search?q=` endpoint over the existing `ft_notes_content(title, content)` FULLTEXT index, using `MATCH ... AGAINST ... IN BOOLEAN MODE` (SRCH-01)
- **MySQL config** so 2-character tokens (e.g. "AI") are searchable (`innodb_ft_min_token_size=2`)
- Tests proving all of the above against **real MySQL** (testcontainers), including per-user isolation of tags and collections

Maps to requirements: **ORG-01, ORG-02, ORG-03, ORG-04, SRCH-01**.

Out of scope (later phases / deferred): local AI summarization & auto-tagging (Phase 5); RAG / embeddings / semantic search (Phase 6); CI/CD + prod (Phase 7). Explicitly deferred this phase: **hybrid full-text + semantic rank fusion (SRCH-02, v2)**, tag rename endpoints, tag/collection colors or descriptions beyond a name, bulk tagging, and search facets/highlighting.

</domain>

<decisions>
## Implementation Decisions

### Tags (ORG-01, ORG-02)
- **D-01:** **Auto-create-on-attach (find-or-create by name).** No separate "create tag" ceremony — tagging a note with a name finds the user's existing tag or creates it, then attaches. (Explicit `POST /tags` was offered; user chose the lighter UX.)
- **D-02:** **Tags are per-user.** The `tags` table carries a `user_id` FK; each user has a private tag namespace. `GET /tags` returns only the caller's tags. (Global shared tags were offered and rejected — they weaken the multi-user isolation story.)
- **D-03:** **Tag names are normalized on the way in** — trimmed + lowercased — so "Python", "python", and " python " collapse to the same tag. Uniqueness is enforced per user on the normalized name (`UNIQUE(user_id, name)`); find-or-create keys off the normalized value.
- **D-04:** **Many-to-many via a `note_tags` join table.** Many notes ↔ many tags.
- **D-05:** **Multi-tag filter is AND (intersection).** `GET /notes?tag=python&tag=docker` returns only notes carrying **both** tags. (OR/union was offered and rejected.) The tag filter lives on the **existing `GET /notes` list endpoint** (per success criterion 1), composing with the existing pagination/sort/`filter` contract and the Phase-3 `user_id` scoping. Use `selectinload` for the tag relationship to avoid N+1 (criterion 1).

### Collections (ORG-03, ORG-04)
- **D-06:** **Collections are many-to-many with notes** (via a `note_collections` join table). A note can belong to several collections at once (e.g. "Work" and "Reading List"); membership is optional. (Folder-style one-to-many was offered and rejected.)
- **D-07:** **Collections are per-user**, mirroring tags — `collections` table has a `user_id` FK; create/list/add/remove are all owner-scoped. Cross-user access to a collection follows the Phase-3 contract (403 if it exists but is owned by another user, 404 if missing).
- **D-08:** REST surface: create a collection, add a note (`POST /collections/{id}/notes`), remove a note, and list its notes (`GET /collections/{id}/notes`). The note-list response should reuse the canonical `NoteListResponse {items,total,page,size,pages}` envelope where a list of notes is returned.

### Full-Text Search (SRCH-01)
- **D-09:** **Standalone `GET /search?q=` endpoint**, returning the same `NoteListResponse` envelope (paginated, user-scoped via `WHERE user_id = current_user`). Search does **not** compose with tag/collection filters this phase (that composition is deferred). (Tag filtering remains on `GET /notes`; search is its own endpoint.)
- **D-10:** **`MATCH(title, content) AGAINST(:q IN BOOLEAN MODE)`** — BOOLEAN MODE so users get `+required` / `-exclude` / `prefix*` operators. (NATURAL LANGUAGE mode was offered and rejected.) Reuses the **already-existing** `ft_notes_content(title, content)` FULLTEXT index from migration `d51191e92276` — no new index needed for the base case.
- **D-11:** **`innodb_ft_min_token_size = 2`** must be set on the MySQL service so 2-char terms ("AI") are indexed and searchable (success criterion 4). This is a **server-startup variable** (read-only at runtime) — it requires setting it before/at container init **and** rebuilding the FULLTEXT index (`OPTIMIZE TABLE` / drop+recreate) for pre-existing rows. Verified via `SHOW VARIABLES LIKE 'innodb_ft_min_token_size'`. The test harness (testcontainers MySQL) must apply the same setting so the 2-char test is reproducible.

### Claude's Discretion (sensible defaults — planner may refine)
- Exact REST shape for tag attach/detach (`POST /notes/{id}/tags` with `{name}` + `DELETE /notes/{id}/tags/{name|id}`) — must satisfy ORG-01; planner picks the cleanest verbs.
- Whether detaching the last note from a tag auto-deletes the orphan tag, or tags persist until explicitly deleted — planner's call (default: persist).
- `ON DELETE CASCADE` behavior for join tables when a note/tag/collection is deleted (default: cascade the join rows).
- Collection name uniqueness per user (`UNIQUE(user_id, name)`) — recommended, planner's call.
- BOOLEAN MODE query sanitization for stray operator characters in `q` (avoid syntax errors from user input) — planner should handle gracefully.
- How `innodb_ft_min_token_size=2` is delivered (compose `command:` arg vs mounted `my.cnf`) and how the index rebuild is sequenced relative to Alembic migrations.
- Whether `GET /search` supports the same `sort` whitelist as `GET /notes`, or sorts by FULLTEXT relevance score by default.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — product context; MySQL learning goal ("modèle relationnel riche attendu : jointures, many-to-many, index, full-text") directly drives this phase
- `.planning/REQUIREMENTS.md` — ORG-01..04, SRCH-01 are the requirements in scope; SRCH-02 (hybrid search) is the deferred v2 sibling
- `.planning/ROADMAP.md` §"Phase 4: Tags, Collections, Full-Text Search" — the 5 success criteria this phase is judged against (tag attach/detach + `?tag=` join no N+1; multi-tag filter; collection add + list; `?q=` MATCH AGAINST BOOLEAN MODE with 2-char tokens; per-user isolation of tags/collections)
- `.planning/STATE.md` §Decisions — canonical pagination envelope (D-06), sort-whitelist + 422 contract, testcontainers strategy

### Research
- `.planning/research/ARCHITECTURE.md` — domain-per-folder layering (Router → Service → Repository) to mirror for new `app/tags/` and `app/collections/` packages
- `.planning/research/STACK.md` — async SQLAlchemy 2.x / asyncmy patterns; `selectinload` for many-to-many; pytest-asyncio + httpx AsyncClient testing
- `CLAUDE.md` §"MySQL Full-Text Search" and §"MySQL + SQLAlchemy 2" — FULLTEXT keyword search guidance; async ORM patterns

### Prior phase carry-forward (the integration foundation this phase builds on)
- `.planning/phases/02-database-api-skeleton/02-CONTEXT.md` — D-06 pagination envelope, D-07 sort whitelist, D-10 domain-per-folder, D-14/15 async DB + Alembic-not-create_all, D-16/17/18 testcontainers strategy
- `.planning/phases/03-auth-per-user-data-isolation/03-CONTEXT.md` — D-07/08/09 per-user scoping + 403/404 ownership contract that tags & collections MUST inherit

### Existing code (integration targets)
- `app/notes/models.py` — `Note` model; add `tags` / `collections` relationships here (already has `title`+`content` and FULLTEXT-index docstring)
- `app/notes/repository.py` — `list_paginated()` is where the `?tag=` AND-filter + `selectinload` integrate; `_SORT_WHITELIST` pattern to reuse for search
- `app/notes/router.py` / `service.py` — `?tag=` query param threads through here; ownership/404-vs-403 pattern (`get_or_404_owned`) to reuse for collections
- `app/notes/schemas.py` — `NoteListResponse` envelope to reuse for `/search` and `/collections/{id}/notes`; add `tags` to `NoteRead`
- `app/core/dependencies.py` — `get_current_user`, `get_db`; add `get_tag_service` / `get_collection_service` / `get_search_service` providers here
- `app/main.py` — register new `tags`, `collections`, `search` routers
- `app/database.py` — shared async `Base`; new `Tag` / `Collection` / join-table models extend it
- `alembic/versions/d51191e92276_create_notes_table.py` — **already creates** `ft_notes_content(title, content)` FULLTEXT index; new migration adds tags/collections/join tables
- `alembic/versions/0003_add_user_id_to_notes.py` — the most recent migration; new migration's `down_revision` chains from here
- `docker-compose.yml` — `mysql:8.4` service; needs `innodb_ft_min_token_size=2` config added (D-11); no MySQL `command:`/`my.cnf` exists yet
- `tests/conftest.py` — testcontainers `mysql:8.4` harness + per-test rollback; extend with tag/collection fixtures and the 2-char-token config (D-11)

No user-referenced external docs/ADRs were introduced during discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/notes/` package** is the exact template for new **`app/tags/`** and **`app/collections/`** packages (router/schemas/models/service/repository) — domain-per-folder is established.
- **`NoteListResponse {items,total,page,size,pages}`** (in `app/notes/schemas.py`) is the canonical list envelope — reuse verbatim for `GET /search` and `GET /collections/{id}/notes`.
- **`NoteService.get_or_404_owned` + repository `get_by_id`** — the 404-vs-403 ownership pattern to copy for collection ownership checks.
- **`_SORT_WHITELIST` dict → ORM column** mapping in `app/notes/repository.py` — the safe "no silent fallback, unknown → 422" pattern; reuse if `/search` accepts sort.
- **`ft_notes_content(title, content)` FULLTEXT index already exists** — search needs the query + endpoint, not a new index (only the `min_token_size` config + rebuild for 2-char tokens).
- **`tests/conftest.py`** testcontainers MySQL + transaction-per-test rollback — extend with tag/collection fixtures.

### Established Patterns
- **Router → Service → Repository**, zero business logic in routers; all SQL in repositories.
- **Alembic migrations, never `Base.metadata.create_all()`** — tags/collections/join tables + the `min_token_size` index rebuild come via a new migration chained from `0003`.
- **Per-user isolation (Phase 3):** every read/write scoped by `user_id`; single-resource endpoints do 404-if-missing / 403-if-wrong-owner. Tags and collections inherit this.
- **utf8mb4 / InnoDB** `__table_args__` on every new model.
- **`selectinload`** for eager-loading many-to-many to avoid N+1 (explicit success criterion).

### Integration Points
- `GET /notes` (`list_paginated`) gains an optional `tag` filter (AND semantics) joined through `note_tags`, layered on top of the existing `user_id` + `filter` + sort + pagination logic.
- `app/main.py` registers three new routers (`tags`, `collections`, `search`).
- `NoteRead` schema gains a `tags` field so tagged notes serialize their tags.
- `docker-compose.yml` mysql service + `tests/conftest.py` MySQL container both need `innodb_ft_min_token_size=2`.

</code_context>

<specifics>
## Specific Ideas

- This is a **learning project** — the phase exists largely to exercise **MySQL relational depth**: many-to-many join tables (tags, collections), `selectinload` to avoid N+1, and FULLTEXT `MATCH ... AGAINST`. Lean toward the teachable-correct relational modeling even when a shortcut exists.
- The end-to-end flow must work via Swagger: create a note → tag it ("python") → `GET /notes?tag=python` returns it → add it to a "Work" collection → `GET /collections/{id}/notes` returns it → `GET /search?q=python` finds it (including a 2-char term like "AI").
- Per-user isolation of tags AND collections must be proven by **integration tests** against real MySQL — user A cannot see/modify user B's tags or collections (mirrors the Phase-3 notes isolation tests).
- The 2-char-token requirement (`innodb_ft_min_token_size=2`) is a known FULLTEXT gotcha — capture it explicitly so the planner doesn't ship a search that silently drops "AI", "Go", "ML".

</specifics>

<deferred>
## Deferred Ideas

- **Hybrid full-text + semantic rank fusion (SRCH-02)** — explicitly a v2 item; this phase is keyword-only FULLTEXT. Semantic/RAG search arrives in Phase 6.
- **Search composing with tag/collection filters** (`GET /notes?q=...&tag=...`) — offered during discussion, deferred (D-09 keeps `/search` standalone this phase).
- **Tag rename endpoint, tag/collection descriptions, colors, icons** — beyond the name-only MVP scope.
- **Bulk tagging / bulk collection assignment** — single-note operations only this phase.
- **Search result highlighting / snippets / facets** — not in SRCH-01.
- **Auto-tagging via LLM** — Phase 5 (local AI), explicitly a different capability from manual tags here.

None of the above is scope creep into Phase 4 — they are correctly sequenced into their own phases / v2.

</deferred>

---

*Phase: 4-Tags, Collections, Full-Text Search*
*Context gathered: 2026-06-28*
