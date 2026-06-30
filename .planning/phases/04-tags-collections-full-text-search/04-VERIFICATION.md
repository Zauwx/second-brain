---
phase: 04-tags-collections-full-text-search
verified: 2026-06-30T07:33:33Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: "Initial verification — no prior VERIFICATION.md existed"
---

# Phase 4: Tags, Collections, Full-Text Search Verification Report

**Phase Goal:** Users can organize notes with tags (many-to-many) and collections, and search notes by keyword using MySQL FULLTEXT — completing the full table-stakes REST surface.
**Verified:** 2026-06-30T07:33:33Z
**Status:** passed
**Re-verification:** No — initial verification

## Methodology Note

The ROADMAP marks this phase `mode: mvp`, but the phase **Goal** is a capability statement, not a `As a … I want to … so that …` User Story (the per-plan goals derive 1:1 user stories from the locked requirements, as the plans explicitly document). Rather than refuse verification on a planning-metadata technicality for a fully-implemented, fully-tested phase, I verified goal-backward against the **5 ROADMAP Success Criteria** (the binding contract) plus all PLAN `must_haves`. This is informational; it is not a blocker. All five criteria are observably satisfied in the codebase and proven by a passing integration suite running against real MySQL 8.4.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | Create tags, attach/detach to notes; `GET /notes?tag=python` returns only tagged notes; many-to-many via `selectinload`, no N+1 | ✓ VERIFIED | `app/tags/{models,repository,service,router}.py` complete; `Note.tags = relationship("Tag", secondary=note_tags)` (models.py:117); `selectinload(Note.tags)` applied in `get_by_id` and `list_paginated` before count (repository.py:67,151 — 4 occurrences total); `GET /tags`, `POST /notes/{id}/tags`, `DELETE /notes/{id}/tags/{name}` wired (router.py); `tests/test_tags.py` (8 tests) + `test_single_tag_filter` PASS |
| 2 | Filter by multiple tags simultaneously (`?tag=python&tag=docker`) — strict AND | ✓ VERIFIED | `list_paginated` builds tag-id scalar subquery + note-id subquery with `having(func.count(note_tags.c.tag_id.distinct()) == len(normalized))` (repository.py:129-146); router exposes repeatable `tag: list[str] = Query()` (notes/router.py:64); `test_multi_tag_and_filter` asserts python-only note excluded — PASS |
| 3 | Create a collection, add notes, `GET /collections/{id}/notes` returns its notes | ✓ VERIFIED | `app/collections/` package complete (model, repository, service, router); `note_collections` join table + `Collection.notes`/`Note.collections_rel` many-to-many (notes/models.py:45-61,124); `list_notes` joins `note_collections`, double-scoped by collection_id + user_id, `selectinload(Note.tags)`, returns `NoteListResponse` envelope; router registered `prefix="/collections"` (main.py:61); `tests/test_collections.py` (6 tests incl. many-to-many) PASS |
| 4 | `GET /search?q=` MATCH AGAINST BOOLEAN MODE; 2-char "AI" returns results; `innodb_ft_min_token_size=2` | ✓ VERIFIED | `app/search/repository.py` uses `from sqlalchemy.dialects.mysql import match` → `match(Note.title, Note.content, against=q).in_boolean_mode()` (parameterized, no text()/f-string); user-scoped `.where(Note.user_id==user_id)`; `sanitize_boolean_query` strips `@`/`++`/trailing operators; `docker-compose.yml:28` `command: --innodb-ft-min-token-size=2`; conftest container sets same; migration 0004 rebuilds `ft_notes_content`; `test_two_char_token_search` (q=AI, total>=1) + 11 search tests PASS |
| 5 | Tags and collections isolated per user — A cannot read/modify B's | ✓ VERIFIED | `get_or_404_owned` (403 wrong owner / 404 missing) in TagService + CollectionService; all list queries scoped to caller `user_id`; tag-filter + search scoped on both Tag.user_id and Note.user_id; `tests/test_phase4_isolation.py` (8 dedicated cross-user tests) + per-slice isolation tests PASS |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/tags/models.py` | Tag ORM, UNIQUE(user_id,name) | ✓ VERIFIED | `class Tag(Base)`, `UniqueConstraint("user_id","name", name="uq_user_tag")` |
| `app/tags/repository.py` | find_or_create SAVEPOINT, list, attach/detach | ✓ VERIFIED | `begin_nested()` SAVEPOINT + IntegrityError re-select; `.strip().lower()` normalize |
| `app/tags/router.py` | GET /tags, POST/DELETE notes tags | ✓ VERIFIED | 3 endpoints, all behind `get_current_user` |
| `alembic/versions/0004_add_tags.py` | tags+note_tags, FULLTEXT rebuild | ✓ VERIFIED | down_revision 0003; two `op.execute` DROP+ADD `ft_notes_content` |
| `app/notes/repository.py` | tag AND-filter + selectinload | ✓ VERIFIED | `having(func.count(...distinct()))`, `selectinload(Note.tags)` |
| `app/collections/models.py` | Collection ORM, UNIQUE(user_id,name) | ✓ VERIFIED | `class Collection(Base)`, `uq_user_collection` |
| `app/collections/router.py` | POST/GET + notes membership | ✓ VERIFIED | 5 endpoints incl. NoteListResponse listing |
| `alembic/versions/0005_add_collections.py` | collections+note_collections | ✓ VERIFIED | down_revision 0004; `note_collections` composite PK CASCADE |
| `app/search/repository.py` | in_boolean_mode | ✓ VERIFIED | `match(...).in_boolean_mode()`, parameterized |
| `app/search/service.py` | sanitize_boolean_query + envelope | ✓ VERIFIED | strips @/++/trailing; empty→empty envelope (no DB hit) |
| `app/search/router.py` | GET /search?q= | ✓ VERIFIED | registered `prefix="/search"` |
| `docker-compose.yml` | min_token_size=2 | ✓ VERIFIED | `command: --innodb-ft-min-token-size=2` |
| `tests/test_tags.py` | ORG-01 + isolation | ✓ VERIFIED | 179 lines, 8 tests, PASS |
| `tests/test_notes_tag_filter.py` | ORG-02 AND filter | ✓ VERIFIED | 103 lines, PASS |
| `tests/test_collections.py` | ORG-03/04 + isolation | ✓ VERIFIED | 167 lines, 6 tests, PASS |
| `tests/test_search.py` | SRCH-01 + 2-char/isolation/sanitize | ✓ VERIFIED | 170 lines, 11 tests, PASS |
| `tests/test_phase4_isolation.py` | consolidated isolation | ✓ VERIFIED | 269 lines, 8 tests referencing user_a/user_b clients, PASS |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| notes/models.py | note_tags / Tag | relationship(secondary=note_tags) | ✓ WIRED | models.py:117 |
| notes/repository.py | Note.tags | selectinload in get_by_id + list_paginated | ✓ WIRED | 4 occurrences (incl. create/update re-fetch) |
| tags/repository.py | tags table | find_or_create begin_nested | ✓ WIRED | repository.py:56 |
| main.py | tags_router | include_router (no prefix) | ✓ WIRED | main.py:60 |
| notes/repository.py | note_tags+Tag | GROUP BY HAVING COUNT(DISTINCT) | ✓ WIRED | repository.py:139-146 |
| notes/models.py | note_collections / Collection | relationship("Collection", secondary) | ✓ WIRED | models.py:124 |
| collections/repository.py | Note via note_collections | join + selectinload(Note.tags) | ✓ WIRED | repository.py:97-103 |
| collections/service.py | ownership | get_or_404_owned 403/404 | ✓ WIRED | service.py:34-54 |
| main.py | collections_router | include_router prefix=/collections | ✓ WIRED | main.py:61 |
| search/repository.py | MySQL FULLTEXT | match().in_boolean_mode() | ✓ WIRED | repository.py:48 |
| search/service.py | repository | sanitize then search_fulltext | ✓ WIRED | service.py:58-61 |
| main.py | search_router | include_router prefix=/search | ✓ WIRED | main.py:62 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full Phase-4 suite (tags, filter, collections, search, isolation) against real MySQL 8.4 | `uv run pytest tests/test_tags.py tests/test_notes_tag_filter.py tests/test_collections.py tests/test_search.py tests/test_phase4_isolation.py -q` | 37 passed in 14.78s | ✓ PASS |
| Full repository suite (no regressions) | `uv run pytest -q` | 109 passed in 19.03s | ✓ PASS |
| 2-char token search (proves min_token_size=2 active) | `test_two_char_token_search` (q=AI → total>=1) | included in pass | ✓ PASS |

Tests run via testcontainers spinning up `mysql:8.4` with `--innodb-ft-min-token-size=2` — i.e. these are true integration behaviors, not mocked. The 2-char-token test passing is direct behavioral confirmation of SC4's `innodb_ft_min_token_size=2` requirement (a result only possible if the variable is ≤ 2).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| ORG-01 | 04-01, 04-05 | Create tags, attach/detach (many-to-many) | ✓ SATISFIED | tags package + tests PASS |
| ORG-02 | 04-02, 04-05 | Filter notes by one or more tags | ✓ SATISFIED | AND-intersection filter + tests PASS |
| ORG-03 | 04-03, 04-05 | Create collections, add/remove notes | ✓ SATISFIED | collections package + tests PASS |
| ORG-04 | 04-03, 04-05 | List notes in a collection | ✓ SATISFIED | GET /collections/{id}/notes envelope + tests PASS |
| SRCH-01 | 04-04, 04-05 | Full-text keyword search (MySQL FULLTEXT) | ✓ SATISFIED | BOOLEAN MODE search + tests PASS |

All 5 phase requirement IDs are accounted for. REQUIREMENTS.md maps exactly ORG-01..04 + SRCH-01 to Phase 4 (all marked Complete), with no orphaned IDs and no IDs claimed by plans but absent from REQUIREMENTS.md.

### Anti-Patterns Found

None in Phase 4 source files. Scan for `TODO|FIXME|XXX|HACK|PLACEHOLDER|not implemented|NotImplementedError` across `app/` returned only pre-existing matches in `app/core/config.py` (intentional secret-refusal/placeholder-detection logic from Phase 1 — not Phase 4 work and not a debt marker). No stub returns: every repository/service method returns real query results; all SUMMARYs declare "Known Stubs: None" and code inspection confirms it.

### Human Verification Required

None. The phase is API-only (no visual/UX surface). SC4's "confirmed via `SHOW VARIABLES`" manual check is behaviorally proven by the passing 2-character-token integration test, which can only succeed when `innodb_ft_min_token_size` ≤ 2; the same flag is set in both `docker-compose.yml` and the test container. No item requires human judgment.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are observably true in the codebase, all PLAN `must_haves` (artifacts + key links) exist, are substantive, and are wired, and the full 109-test suite passes against real MySQL 8.4 — including 37 Phase-4-specific tests covering tag CRUD, AND-intersection filtering, collection membership, BOOLEAN MODE search with 2-char tokens and operator sanitization, and exhaustive cross-user isolation. The only observation is a planning-metadata mismatch (phase `mode: mvp` with a non-User-Story Goal); this is informational and does not affect goal achievement.

---

_Verified: 2026-06-30T07:33:33Z_
_Verifier: Claude (gsd-verifier)_
