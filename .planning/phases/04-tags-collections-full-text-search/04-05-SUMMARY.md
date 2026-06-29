---
phase: 04-tags-collections-full-text-search
plan: 05
subsystem: isolation-gate
tags: [isolation, security, T-04-iso, tags, collections, search, tag-filter, ORG-01, ORG-02, ORG-03, ORG-04, SRCH-01]
dependency_graph:
  requires: [04-01-tags-vertical-slice, 04-02-tag-filter, 04-03-collections-vertical-slice, 04-04-search-vertical-slice]
  provides: [tests/test_phase4_isolation.py, "Phase-4 success criterion 5 verified"]
  affects: []
tech_stack:
  added: []
  patterns:
    - user_a_client/user_b_client fixtures for cross-user 403/404 assertions
    - rollback-session isolation for tag/collection assertions
    - FULLTEXT non-leakage assertion via total==0 (uncommitted data not indexed by InnoDB)
key_files:
  created:
    - tests/test_phase4_isolation.py
  modified: []
decisions:
  - "Rollback-session fixtures used for search isolation test — InnoDB FULLTEXT does not index uncommitted data; total==0 is the correct isolation assertion and matches existing test_search_isolation pattern"
  - "Eight separate test functions (not one mega-test) — each resource boundary gets its own named assertion for clear failure attribution"
  - "test_missing_collection_returns_404 uses user_b_client alone — proves 404 for genuinely missing resource, distinct from 403 for owned-by-other"
metrics:
  duration_minutes: 10
  completed_date: "2026-06-29"
  tasks_completed: 1
  files_touched: 1
---

# Phase 4 Plan 05: Cross-User Isolation Gate Summary

**One-liner:** Consolidated Phase-4 isolation proof (success criterion 5) — 8 exhaustive tests spanning tags, collections, search, and tag-filter confirm zero cross-user data leakage and correct 403/404 ownership contract; 109-test full suite green.

## What Was Built

Delivered `tests/test_phase4_isolation.py` — the single authoritative end-to-end isolation gate for Phase 4:

**Tag isolation (T-04-02, T-04-iso):**
- `test_tag_list_does_not_leak_across_users` — User B's `GET /tags` never returns a tag created by user A. Verifies `list_by_user` scopes to `caller.user_id`.
- `test_tag_detach_on_other_users_note_returns_403` — `DELETE /notes/{A_note_id}/tags/{name}` by user B returns 403. Verifies `TagService.get_or_404_owned` enforces note ownership before allowing detach.

**Collection isolation (T-04-06, T-04-07, T-04-iso):**
- `test_collection_list_does_not_leak_across_users` — User B's `GET /collections/` never lists user A's collections. Verifies `list_by_user` scoped to caller.
- `test_collection_notes_on_other_users_collection_returns_403` — `GET /collections/{A_id}/notes` returns 403 for user B. Verifies `get_or_404_owned` raises 403 for wrong owner.
- `test_add_note_to_other_users_collection_returns_403` — `POST /collections/{A_id}/notes` returns 403 when B tries to inject a note into A's collection.
- `test_missing_collection_returns_404` — `GET /collections/999999/notes` returns 404 for a non-existent collection. Verifies the 403-vs-404 contract: missing resource always 404.

**Search isolation (T-04-iso):**
- `test_search_does_not_leak_across_users` — `GET /search/?q={unique_term}` returns `total==0` for user B when the term only appears in user A's notes. Verifies `WHERE Note.user_id == caller.id` in `SearchRepository.search_fulltext`.

**Tag-filter isolation (T-04-04, T-04-iso):**
- `test_tag_filter_does_not_leak_across_users` — `GET /notes/?tag={a_private_tag}` returns `total==0` for user B when the tag is only attached to user A's notes. Verifies both `Tag.user_id == caller.id` (tag subquery) and `Note.user_id == caller.id` (outer query) are enforced in `NoteRepository.list_paginated`.

## Verification

- `uv run pytest tests/test_phase4_isolation.py -q` — **8 passed, 0 failed**
- `uv run pytest -q` (full suite) — **109 passed, 0 failed** (Phase-4 gate confirmed)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

- **T-04-iso:** All four resource surfaces (tags, collections, search, tag-filter) explicitly tested for cross-user data leakage — zero leakage confirmed.
- **T-04-04:** Tag-filter isolation test confirms parameterized subquery scoping; no injection surface.
- **T-04-SC:** No new packages installed.

## Known Stubs

None. All assertions exercise real MySQL data paths via the existing vertical slice implementations.

## Threat Flags

None. No new network surfaces introduced. This plan creates only test code.

## Self-Check: PASSED

- `tests/test_phase4_isolation.py` — FOUND (269 lines, 8 test functions)
- Commit 448ee7f — FOUND in git log
- 109 tests passed, 0 failed (full suite)
