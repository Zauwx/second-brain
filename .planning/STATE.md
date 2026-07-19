---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 05-03-PLAN.md
last_updated: "2026-07-06T17:12:00.900Z"
last_activity: 2026-07-06
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 18
  completed_plans: 18
  percent: 71
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-23)

**Core value:** User can save content and retrieve / query their knowledge in natural language (RAG)
**Current focus:** Phase 05 — local-ai-ollama

## Current Position

Phase: 05 (local-ai-ollama) — EXECUTING
Plan: 4 of 4
Status: Live checkpoint in progress (steps 1-3 pass, resuming at step 4)
Last activity: 2026-07-19 - Completed quick task 260719-snb: alembic assets + venv PATH into api image

Progress: [█████████░] 94%

## Performance Metrics

**Velocity:**

- Total plans completed: 14
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | - | - |
| 02 | 3 | - | - |
| 03 | 3 | - | - |
| 04 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01-repo-foundation P01 | 3 | 3 tasks | 5 files |
| Phase 01-repo-foundation P02 | 12 | 3 tasks | 14 files |
| Phase 01-repo-foundation P03 | 40 | 5 tasks | 4 files |
| Phase 02 P02 | 20 | 3 tasks | 8 files |
| Phase 02 P03 | 9 | 2 tasks | 3 files |
| Phase 04 P01 | 45 | 3 tasks | 14 files |
| Phase 04 P02 | 15 | 2 tasks | 4 files |
| Phase 04 P03 | 20 | 3 tasks | 11 files |
| Phase 04 P04 | 20 | 2 tasks | 10 files |
| Phase 04 P05 | 10 | 1 tasks | 1 files |
| Phase 05 P01 | 12 | 3 tasks | 5 files |
| Phase 05 P02 | 56min | 3 tasks | 9 files |
| Phase 05 P03 | 6min | 3 tasks | 11 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-Phase 1]: Embeddings stored as MySQL JSON columns in `note_chunks` (not Qdrant/ChromaDB); cosine similarity computed in Python — correct for personal scale < 50k chunks. Upgrade path documented in SUMMARY.md.
- [Pre-Phase 1]: Use `asyncmy` (not `aiomysql`), `pwdlib[argon2]` (not passlib), `PyJWT` (not python-jose) — all deprecated replacements identified before first line of code.
- [Pre-Phase 1]: Python pinned to 3.12 in Dockerfiles; `python:3.12-slim` base image (not Alpine).
- [Phase 6 flag]: Before writing first embed call, confirm MySQL 8.4 JSON columns vs MySQL 9.0+ VECTOR type vs Qdrant — decision must be made explicit at Phase 6 planning time.
- [Phase ?]: Repo hygiene layer complete
- [Phase ?]: LF enforcement set
- [Phase ?]: CI badge deferred to Phase 7
- [Phase 1 Plan 02]: Python pinned to 3.12 via .python-version — uv defaulted to 3.14; CLAUDE.md requires 3.12
- [Phase 1 Plan 02]: Used PEP 735 [dependency-groups] instead of deprecated [tool.uv.dev-dependencies]
- [Phase 1 Plan 02]: Settings extra=ignore — future-phase env vars (MySQL/JWT/Anthropic/Ollama) ignored at Phase-1 startup
- [Phase ?]: D-01/D-02: GitHub repo second-brain created as PUBLIC from first push — permanent portfolio history
- [Phase ?]: D-12: python:3.12-slim (not Alpine) chosen to support asyncmy Cython and cryptography C extensions in later phases
- [Phase ?]: Secret isolation: .dockerignore + no COPY .env + env_file at runtime = three independent protection layers
- [Phase ?]: NoteListResponse{items,total,page,size,pages} is the canonical pagination envelope (D-06)
- [Phase ?]: testcontainers mysql:8.4 + alembic upgrade head replaces SQLite for all Note tests
- [Phase ?]: Routes at /notes/ (trailing slash) and /notes/{note_id} — httpx does not follow redirects
- [Phase ?]: Sort whitelist dict maps created_at/updated_at tokens to ORM columns; unknown token raises ValueError→422 (no silent fallback)
- [Phase ?]: Service layer translates repository ValueError to HTTPException 422 to prevent 500 leaking internal errors (T-02-14)
- [Phase 04 Plan 01]: Two migrations (0004 tags, 0005 collections) instead of one — keeps each vertical slice's migration self-contained
- [Phase 04 Plan 01]: NoteRepository.create/update use get_by_id re-fetch after commit — session.refresh() exposes MissingGreenlet on Note.tags in async context
- [Phase ?]: [Phase 05 Plan 01]: ollama Compose service uses top-level mem_limit: 4g (not deploy.resources) since plain docker compose up ignores the Swarm key (D-09)
- [Phase ?]: [Phase 05 Plan 01]: ollama healthcheck is [CMD, ollama, list] not curl — the ollama/ollama image ships no curl binary
- [Phase ?]: [Phase 05 Plan 02]: get_llm_provider is a plain sync function (no async needed for OllamaProvider construction), matching RESEARCH.md's Dependency wiring example verbatim
- [Phase ?]: [Phase 05 Plan 02]: ai_client fixture deletes only the get_llm_provider override key on teardown (not a blanket clear()) since it runs before the underlying client fixture's own clear() in reverse-dependency teardown order
- [Phase 05]: [Phase 05 Plan 03]: AIService reuses NoteService.get_or_404_owned; _safe_complete is the only place raising HTTPException(503), catching ConnectionError/TimeoutError/OSError/ollama.ResponseError
- [Phase 05]: [Phase 05 Plan 03]: Summarize response reuses NoteRead instead of a bespoke SummarizeResponse schema
- [Phase 05]: [Phase 05 Plan 03]: retry-then-succeed test fake implements its own internal tenacity retry mirroring OllamaProvider, since AIService calls provider.complete() exactly once per request
- [Phase 05 Plan 04]: _parse_tag_list implemented verbatim from RESEARCH.md Pattern 4 (json.loads -> regex [...] fallback -> dict-unwrap -> coerce -> []); AIService.suggest_tags has no write path at all, structurally enforcing suggest-only D-04

### Pending Todos

None yet.

### Blockers/Concerns

yet.

- **BLOCKING — criterion 3 FAILS: `POST /ai/suggest-tags` always returns `{"tags": []}` in the real stack.** Root cause found in the 05-04 live checkpoint: `AIService.suggest_tags` calls the provider with `json_mode=True` → `format="json"`, which pushes llama3.2:3b to emit an OBJECT. It mimics the prompt's own placeholder example `["tag-one","tag-two"]` as KEYS, producing e.g. `{"tag-one":"language-models","tag-two":"nlp-techniques"}`. `_parse_tag_list`'s dict-unwrap looks for a dict value that IS a list; all values are strings, so nothing matches and it falls through to `return []` — HTTP 200 with an empty list, no warning logged. Mocked tests never caught it because they feed the parser hand-written strings and never exercise real model behavior under the production flag.
  Verified fix candidate (3/3 clean runs): pass an explicit JSON schema as `format=` instead of `"json"` → `{"tags":["rag","retrieval","augmented-generation"]}`, which the EXISTING parser already unwraps correctly. Also drop/reword the `["tag-one","tag-two"]` example in `build_tag_prompt` — with `format=""` the model copies it as a literal `tag-` prefix in 2/3 runs.
- Phase 05 CANNOT be signed off until the above is fixed and criterion 3 re-verified against the live stack.
- 05-04 live checkpoint results: step 1 ✓ stack up; step 2 ✓ llama3.2:3b pulled; step 3 ✓ /health ok; step 4 ✓ summarize 13s, accurate 3-sentence summary, persisted (criterion 2); step 5 ✗ suggest-tags empty (criterion 3); step 6 ✓ ollama peak 2.479GiB/4GiB (criterion 4); step 7 ✓ clean 503 + notes CRUD unaffected + /health "unreachable" (D-07); step 8 ✓ 128 passed (criterion 5).
- `/health` reports `"ollama": "ok"` when zero models are pulled — it tracks reachability honestly (correctly showed "unreachable" when ollama was stopped) but not model availability, so it can read green while every AI endpoint fails with "model not found". Discovered during the 05-04 live checkpoint. Not yet triaged.
- 05-04-PLAN.md Task 3 checkpoint steps omit any `alembic upgrade head` step, going from `compose up` straight to registering a user — that sequence cannot work on a fresh volume. Plan text needs correcting.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260719-snb | fix: COPY alembic.ini + alembic/ into api image so migrations can run in-container | 2026-07-19 | 29d4b73 | [260719-snb-fix-copy-alembic-ini-alembic-into-api-im](./quick/260719-snb-fix-copy-alembic-ini-alembic-into-api-im/) |

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2 | IO-01: Bulk Markdown import/export | Deferred | Initial scoping |
| v2 | SRCH-02: Hybrid full-text + semantic search (rank fusion) | Deferred | Initial scoping |

## Session Continuity

Last session: 2026-07-06T16:52:16.612Z
Stopped at: Completed 05-03-PLAN.md
Resume file: None
