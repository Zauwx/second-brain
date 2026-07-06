---
phase: 05-local-ai-ollama
plan: 04
subsystem: api
tags: [ollama, json-parsing, fastapi-dependency-injection, note-tags]

# Dependency graph
requires:
  - phase: 05-local-ai-ollama
    plan: "05-03"
    provides: AIService (summarize + _safe_complete 503-translation), get_ai_service DI composition, app/ai/{prompts,schemas,service,router}.py slice pattern
provides:
  - "POST /ai/suggest-tags — suggest-only, returns a JSON list of tag strings, never attaches/persists (AIL-02, criterion 3, D-04)"
  - "AIService.suggest_tags — reuses get_or_404_owned + _safe_complete, calls provider with json_mode=True"
  - "_parse_tag_list — module-level lenient parser (json.loads -> regex [...] fallback -> dict-unwrap -> coerce -> []), never raises (D-05)"
  - "build_tag_prompt — same delimiter + truncation-guard shape as build_summarize_prompt (T-05-04, T-05-02)"
affects: [phase-06-rag]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_parse_tag_list mirrors app/search/service.py's sanitize_boolean_query shape: pure module-level function, degrades to a safe empty value instead of raising, never touches HTTPException"
    - "Second AI endpoint (suggest-tags) reuses the exact AIService/get_ai_service/router composition established by summarize in 05-03 — no new DI seam needed"

key-files:
  created:
    - tests/ai/test_suggest_tags.py
  modified:
    - app/ai/prompts.py
    - app/ai/schemas.py
    - app/ai/service.py
    - app/ai/router.py

key-decisions:
  - "_parse_tag_list implemented verbatim from RESEARCH.md Pattern 4 (json.loads -> regex first [...] block -> unwrap single list-valued dict -> lowercase/strip/coerce -> default []) — no deviation from the researched shape"
  - "suggest_tags deliberately calls only get_or_404_owned + _safe_complete + _parse_tag_list — no NoteRepository write, no TagService call — enforcing D-04 (suggest-only) at the service layer, not just by omission in the router"

patterns-established:
  - "app/ai/ now exposes two complete router->service->provider slices (summarize, suggest-tags) sharing one AIService — Phase 6 (RAG) can add a third method the same way"

requirements-completed: [AIL-02]

# Metrics
duration: 4min
completed: 2026-07-06
---

# Phase 5 Plan 04: Suggest-Tags Feature Slice Summary

**POST /ai/suggest-tags returns a leniently-parsed JSON list of tag strings from the local LLM, suggest-only (no attach, no persist), reusing the summarize slice's ownership/503 contract — automated tasks complete; live end-to-end phase verification (Task 3) is a pending checkpoint requiring the human to run the real Ollama stack.**

## Performance

- **Duration:** 4 min (Task 1 RED commit to Task 2 GREEN commit)
- **Started:** 2026-07-06T15:43:58+02:00
- **Completed (automated tasks):** 2026-07-06T15:45:58+02:00
- **Tasks:** 2 of 3 (Task 3 is a live human-verify checkpoint, not yet run)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `tests/ai/test_suggest_tags.py` — five behaviors written RED-first: list-only response with `json_mode=True` + suggest-only (tags/summary unchanged on GET), lenient-parse unit test (dict-wrapped, prose-polluted, garbage), 403 wrong-owner, 404 missing-note, 503-on-Ollama-down; zero `unittest.mock`, reusing the `FakeLLMProvider`/`ai_client` seam from 05-02/05-03
- `app/ai/prompts.py::build_tag_prompt` — instructs the model to return ONLY a JSON list of 3-5 short lowercase tags, reusing the same `NOTE CONTENT` delimiters + 8000-char truncation guard as `build_summarize_prompt` (T-05-04, T-05-02)
- `app/ai/schemas.py` — `SuggestTagsRequest{note_id}` / `SuggestTagsResponse{tags: list[str]}`
- `app/ai/service.py::_parse_tag_list` — module-level lenient parser implemented verbatim from RESEARCH.md Pattern 4; never raises, degrades to `[]` on any parse failure (D-05, T-05-07)
- `app/ai/service.py::AIService.suggest_tags` — composes `get_or_404_owned` (T-05-03) + `_safe_complete(..., json_mode=True)` + `_parse_tag_list`; does not call `set_summary` or any tag-attach logic (D-04)
- `POST /ai/suggest-tags` registered in `app/ai/router.py` with the same `401/403/404/503` responses table as `/ai/summarize`

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing suggest-tags test suite** — `042a3ef` (test)
2. **Task 2 (GREEN): suggest_tags + lenient parser + POST /ai/suggest-tags** — `0ef18c3` (feat)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS, committed separately)

**Task 3 (checkpoint:human-verify, gate="blocking"): Live end-to-end phase verification** — NOT YET RUN. See "Pending Checkpoint" below.

## Files Created/Modified
- `tests/ai/test_suggest_tags.py` — RED-then-GREEN test suite for the suggest-tags slice (5 tests)
- `app/ai/prompts.py` — added `build_tag_prompt`
- `app/ai/schemas.py` — added `SuggestTagsRequest`, `SuggestTagsResponse`
- `app/ai/service.py` — added `_parse_tag_list` (module-level) and `AIService.suggest_tags`
- `app/ai/router.py` — added `POST /suggest-tags`

## Decisions Made
- `_parse_tag_list` was implemented exactly as researched in RESEARCH.md Pattern 4, with no local deviation — try/except json.loads, regex `\[.*\]` fallback, dict-unwrap, coerce/normalize, default `[]`.
- `suggest_tags` intentionally has no write path at all (no repository call, no `TagService` composition) so that D-04 (suggest-only) is structurally enforced, not just an omission that a future edit could accidentally reintroduce.

## Deviations from Plan

None — plan executed exactly as written for Tasks 1 and 2.

## Issues Encountered
None.

## User Setup Required

**Task 3 (live checkpoint) is pending and requires manual verification against a real running stack.** See "Pending Checkpoint" below for the exact commands. This is expected per the plan (`autonomous: false`, ends with `checkpoint:human-verify` gate="blocking") — it is not a blocker introduced by this execution, it is the plan's designed final gate.

## Pending Checkpoint

**Task 3: Live end-to-end phase verification (all 5 ROADMAP criteria)** — awaiting human execution. Automated code (Tasks 1-2) is committed and the full mocked suite is green; this checkpoint proves the stack works against a REAL Ollama instance, which the test suite deliberately never touches (criterion 5, D-10).

Exact steps (from 05-04-PLAN.md Task 3):
1. `docker compose up -d` — confirm api, mysql, and ollama all start; `docker compose ps` shows ollama healthy.
2. One-time model pull (fresh volume): `docker compose exec ollama ollama pull llama3.2:3b` (~2GB; only needed once per `ollama_data` volume).
3. `curl -s localhost:8000/health` → shows `"ollama": "ok"` (criterion 1).
4. In Swagger (http://localhost:8000/docs): register/login, create a note with a paragraph of content, then `POST /ai/summarize {note_id}` → returns a 2-3 sentence summary within the timeout; `GET /notes/{id}` shows the persisted `summary` (criterion 2).
5. `POST /ai/suggest-tags {note_id}` → returns a JSON list of tag strings (criterion 3). Optionally attach one via `POST /notes/{id}/tags`.
6. While a summarize call runs, watch `docker stats` — the ollama container stays under its `mem_limit: 4g` (criterion 4).
7. `docker compose stop ollama`, then `POST /ai/summarize` → clean 503 while `GET`/`POST /notes` still works (D-07).
8. Confirm `uv run pytest tests/ -q` still exits 0 (criterion 5 — zero real Ollama calls in the suite; already verified in this execution: 128 passed).

## Next Phase Readiness
- Both `/ai/summarize` and `/ai/suggest-tags` are implemented and unit/integration tested against the mocked provider seam (128 tests passing, no regression from 05-03's 123).
- `uv run ruff check app/ai` clean.
- Phase 5 (AIL-01, AIL-02) code is functionally complete pending the Task 3 live sign-off, which is a human-run checkpoint, not further code work.
- No blockers on the code side. The live checkpoint is the only remaining item before Phase 5 can be marked done in STATE.md/ROADMAP.md.

## Self-Check: PASSED

- `tests/ai/test_suggest_tags.py` — present (created).
- `app/ai/prompts.py`, `app/ai/schemas.py`, `app/ai/service.py`, `app/ai/router.py` — present (modified).
- Commits `042a3ef`, `0ef18c3` — present in git history (`git log --oneline -5`).
- Automated verification: `uv run pytest tests/ai/test_suggest_tags.py -q` → 5 passed; `uv run ruff check app/ai` → all checks passed; `uv run pytest tests/ -q` → 128 passed (no regression).

## TDD Gate Compliance

Task-level RED/GREEN gate sequence verified in git log:
- RED: `042a3ef test(05-04): add failing suggest-tags test suite (RED)`
- GREEN: `0ef18c3 feat(05-04): implement suggest_tags + lenient parser + POST /ai/suggest-tags (GREEN)`

Both gates present in correct order — no warning needed.

---
*Phase: 05-local-ai-ollama*
*Completed: pending (Task 3 live checkpoint outstanding)*
