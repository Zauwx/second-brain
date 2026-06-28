# Phase 4: Tags, Collections, Full-Text Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-28
**Phase:** 4-Tags, Collections, Full-Text Search
**Areas discussed:** Tag model, Tag filter logic, Collections, Search

---

## Tag model (creation & identity)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-create on attach, per-user, normalized | Find-or-create tag by name when tagging; tags scoped per user; names trimmed + lowercased | ✓ |
| Explicit POST /tags first, then attach by id | Tags are first-class resources created explicitly, attached by id | |
| Global shared tags (not per-user) | One shared tag namespace; weaker isolation | |

**User's choice:** Auto-create on attach, per-user, normalized
**Notes:** Lighter UX — no separate create step. `UNIQUE(user_id, name)` on the normalized name; "Python" == "python".

---

## Tag filter logic (multi-tag)

| Option | Description | Selected |
|--------|-------------|----------|
| AND — notes having ALL the tags | `?tag=python&tag=docker` → intersection | ✓ |
| OR — notes having ANY of the tags | `?tag=python&tag=docker` → union | |

**User's choice:** AND (intersection)
**Notes:** Filter lives on the existing `GET /notes` endpoint (per success criterion 1), composing with pagination/sort/filter + user_id scoping. `selectinload` to avoid N+1.

---

## Collections (cardinality)

| Option | Description | Selected |
|--------|-------------|----------|
| Many-to-many (note in multiple collections) | `note_collections` join table; note can be in several collections | ✓ |
| One-to-many (folder-like, one per note) | `collection_id` FK on notes; note in at most one | |

**User's choice:** Many-to-many
**Notes:** Per-user collections, mirrors the tags join-table pattern. Membership optional. Cross-user access follows Phase-3 403/404 contract.

---

## Search behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone GET /search?q=, BOOLEAN MODE, paginated | Dedicated endpoint, NoteListResponse envelope, MATCH AGAINST IN BOOLEAN MODE, user-scoped, no filter composition | ✓ |
| Search composes with tag/collection filters | `GET /notes?q=...&tag=...` unified list endpoint | |
| Standalone, NATURAL LANGUAGE mode | Dedicated endpoint, relevance-ranked, no operators | |

**User's choice:** Standalone GET /search?q=, BOOLEAN MODE, paginated
**Notes:** Reuses existing `ft_notes_content(title, content)` FULLTEXT index. BOOLEAN MODE for +/-/* operators. Filter composition deferred. Requires `innodb_ft_min_token_size=2` for 2-char tokens (criterion 4).

---

## Claude's Discretion

- Exact REST verbs for tag attach/detach and collection note add/remove
- Orphan-tag cleanup policy (default: persist)
- Join-table `ON DELETE CASCADE` behavior
- Collection name uniqueness per user
- BOOLEAN MODE query sanitization for stray operator chars
- Delivery mechanism for `innodb_ft_min_token_size=2` (compose `command:` vs `my.cnf`) and index-rebuild sequencing
- Whether `/search` honors the sort whitelist or defaults to relevance score

## Deferred Ideas

- Hybrid full-text + semantic rank fusion (SRCH-02, v2)
- Search composing with tag/collection filters
- Tag rename, descriptions, colors/icons
- Bulk tagging / bulk collection assignment
- Search highlighting / snippets / facets
- LLM auto-tagging (Phase 5)
