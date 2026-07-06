---
phase: 05-local-ai-ollama
plan: 03
subsystem: api
tags: [ollama, alembic, fastapi-dependency-injection, tenacity, note-summary]

# Dependency graph
requires:
  - phase: 05-local-ai-ollama
    plan: "05-02"
    provides: LLMProvider protocol, OllamaProvider, get_llm_provider DI seam, FakeLLMProvider/ai_client test fixtures
provides:
  - "POST /ai/summarize — synchronous, persists a 2-3 sentence summary via the local LLM (AIL-01, criterion 2, D-01/D-02/D-03)"
  - "Note.summary nullable column + migration 0006_add_note_summary (chained from 0005_add_collections)"
  - "NoteRepository.set_summary — server-side-only persistence write, separate from update()"
  - "AIService — first consumer of the LLMProvider seam; composes NoteService.get_or_404_owned + _safe_complete 503 translation"
  - "get_ai_service DI composition in app/core/dependencies.py"
affects: [05-04, phase-06-rag]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AIService composes the real NoteService for ownership (404/403) instead of re-implementing the check — DRYer than the TagService precedent"
    - "Service-layer-only HTTPException: provider/repository raise plain exceptions; only AIService._safe_complete raises HTTPException(503)"
    - "ollama.ResponseError added to the 503-translation catch list alongside ConnectionError/TimeoutError/OSError so a not-yet-pulled model degrades to 503, not 500"
    - "Prompt content wrapped in explicit NOTE CONTENT delimiters + bounded truncation (8000 chars) as a forward-compatible prompt-injection habit ahead of Phase 6 cross-note retrieval"

key-files:
  created:
    - app/ai/prompts.py
    - app/ai/schemas.py
    - app/ai/service.py
    - app/ai/router.py
    - alembic/versions/0006_add_note_summary.py
    - tests/ai/test_summarize.py
  modified:
    - app/notes/models.py
    - app/notes/schemas.py
    - app/notes/repository.py
    - app/core/dependencies.py
    - app/main.py

key-decisions:
  - "Summarize response reuses NoteRead (not a bespoke SummarizeResponse) — returns the full persisted note, matching criterion 2 without redefining fields the Notes domain already owns"
  - "Retry-then-succeed test fake wraps its own complete() in the SAME tenacity @retry shape OllamaProvider uses, rather than raising the ConnectionError up to AIService — AIService only ever calls provider.complete() once per request, so the retry boundary genuinely lives inside the provider, not the service"
  - "ai_client-only tests (no separate auth) needed an explicit auth_client fixture added too — ai_client wraps the same underlying `client` object but does not itself authenticate it; discovered while running the RED suite for the first time"

patterns-established:
  - "app/ai/ now has the full router->service->provider slice for one capability (summarize) — 05-04 (suggest-tags) adds a second endpoint reusing the same AIService/get_ai_service composition"

requirements-completed: [AIL-01]

# Metrics
duration: 6min
completed: 2026-07-06
---

# Phase 5 Plan 03: Summarize Feature Slice Summary

**POST /ai/summarize synchronously generates and persists a 2-3 sentence local-LLM summary on the caller's own note, surfaced on GET /notes/{id}, with 403/404 ownership and a clean 503 on Ollama failure.**

## Performance

- **Duration:** 6 min (measured from context-load completion to final task commit; upstream research/pattern reads not included)
- **Started:** 2026-07-06T12:41:25Z
- **Completed:** 2026-07-06T12:47:17Z
- **Tasks:** 3 (1 RED test task + 2 GREEN implementation tasks)
- **Files modified:** 11 (6 created, 5 modified)

## Accomplishments
- `tests/ai/test_summarize.py` — five behaviors written RED-first: persist+surface, 503-on-down, retry-then-succeed, 403 wrong-owner, 404 missing-note; zero `unittest.mock`, all via the `FakeLLMProvider`/`ai_client` seam from 05-02
- `alembic/versions/0006_add_note_summary.py` adds a nullable `notes.summary` TEXT column, chained from `0005_add_collections` — `Note.summary` and `NoteRead.summary` now surface it end-to-end
- `NoteRepository.set_summary` persists the AI-generated summary via the same commit→re-fetch→assert-not-None shape as `update()`, kept separate because `NoteUpdate`'s client-facing validation doesn't apply to this server-side write
- `AIService.summarize` composes the real `NoteService.get_or_404_owned` (no duplicated ownership check, T-05-03) then calls `_safe_complete`, which is the only place in the new code that raises `HTTPException` — translating `ConnectionError`/`TimeoutError`/`OSError`/`ollama.ResponseError` to a clean 503 (D-07, Pitfall 1)
- `POST /ai/summarize` registered under `/ai` with a `401/403/404/503` responses table, wired via a new `get_ai_service` DI composition in `app/core/dependencies.py`

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing summarize test suite** — `f9a12a3` (test)
2. **Task 2 (GREEN): Note.summary column + migration 0006 + persistence** — `8a720f1` (feat)
3. **Task 3 (GREEN): AIService.summarize + POST /ai/summarize wiring** — `52d0ab2` (feat)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS, committed separately)

## Files Created/Modified
- `tests/ai/test_summarize.py` — RED-then-GREEN test suite for the summarize slice (5 tests)
- `alembic/versions/0006_add_note_summary.py` — migration adding nullable `notes.summary`
- `app/notes/models.py` — `Note.summary: Mapped[str | None]` TEXT column
- `app/notes/schemas.py` — `NoteRead.summary: str | None`
- `app/notes/repository.py` — `NoteRepository.set_summary`
- `app/ai/prompts.py` — `build_summarize_prompt` with delimiters + bounded truncation
- `app/ai/schemas.py` — `SummarizeRequest{note_id}`
- `app/ai/service.py` — `AIService` (summarize + `_safe_complete`)
- `app/ai/router.py` — `POST /ai/summarize`
- `app/core/dependencies.py` — `get_ai_service`
- `app/main.py` — registers `ai_router` under `/ai`

## Decisions Made
- Reused `NoteRead` as the summarize response schema rather than defining a bespoke `SummarizeResponse` — the full persisted note (with `summary` populated) already satisfies criterion 2, and avoids a parallel schema that would drift from `NoteRead`.
- The retry-then-succeed test fake (`_RetryThenSucceedProvider`) implements its own internal `tenacity` `@retry` (mirroring `OllamaProvider`'s exact decorator shape) rather than letting the raised `ConnectionError` propagate to `AIService`. This is because `AIService.summarize` calls `provider.complete()` exactly once per request — the bounded retry is a provider-internal concern (D-08), so the test fake must retry internally to faithfully exercise that boundary without a real network call.
- Discovered while running the RED suite for the first time that `ai_client` (which overrides `get_llm_provider`) does **not** itself authenticate the underlying `client` — two tests needed an added `auth_client` fixture parameter alongside `ai_client` to register+login the shared client object before hitting `/notes/`.

## Deviations from Plan

None — plan executed exactly as written for all three tasks. The two test-suite corrections above (adding `auth_client` to two test signatures; giving the retry fake its own internal `tenacity` retry) were made during Task 1's RED-to-GREEN iteration, before Task 1 was committed, and are documented here as authoring corrections rather than plan deviations — the plan's own task description explicitly left the retry-fake's exact shape to implementation discretion ("either add a small local fake ... OR assert the OllamaProvider-level retry indirectly").

## Issues Encountered
None beyond the test-authoring corrections described above.

## User Setup Required
None — no external service configuration required. This plan's tests never call a real Ollama instance (D-10); the one-time `docker compose exec ollama ollama pull llama3.2:3b` step (deferred since 05-01/05-02) remains a 05-04-or-later manual verification concern, not a blocker for this plan's automated tests.

## Next Phase Readiness
- `AIService`/`get_ai_service`/`app/ai/router.py` establish the full router→service→provider slice pattern; 05-04 (`suggest-tags`) adds a second endpoint that reuses the same `AIService` composition and `_safe_complete` 503-translation helper.
- `Note.summary` is persisted and surfaced — Phase 6's RAG retrieval can optionally use it as a cheaper embedding input later, though that decision is out of this plan's scope.
- Full suite: 123 passed (no regression). `uv run ruff check app/` clean.
- No blockers.

## Self-Check: PASSED

- `tests/ai/test_summarize.py`, `alembic/versions/0006_add_note_summary.py`, `app/ai/prompts.py`, `app/ai/schemas.py`, `app/ai/service.py`, `app/ai/router.py` — all present (created).
- `app/notes/models.py`, `app/notes/schemas.py`, `app/notes/repository.py`, `app/core/dependencies.py`, `app/main.py` — all present (modified).
- Commits `f9a12a3`, `8a720f1`, `52d0ab2` — all present in git history (`git log --oneline -5`).
- Automated verification: `uv run python -c "... assert 'summary' in Note.__table__.columns ..."` → `ok`; `uv run ruff check app/notes alembic/versions/0006_add_note_summary.py` → all checks passed; `uv run pytest tests/ai/test_summarize.py -q` → 5 passed; `uv run ruff check app/ai app/core/dependencies.py app/main.py` → all checks passed; `uv run pytest tests/ -q` → 123 passed (no regression).

## TDD Gate Compliance

Plan-level RED/GREEN gate sequence verified in git log:
- RED: `f9a12a3 test(05-03): add failing summarize test suite (RED)`
- GREEN: `8a720f1 feat(05-03): add Note.summary column + migration 0006 + set_summary (GREEN)`
- GREEN: `52d0ab2 feat(05-03): implement AIService.summarize + POST /ai/summarize (GREEN)`

Both gates present in correct order — no warning needed.

---
*Phase: 05-local-ai-ollama*
*Completed: 2026-07-06*
