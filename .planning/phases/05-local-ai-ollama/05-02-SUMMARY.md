---
phase: 05-local-ai-ollama
plan: 02
subsystem: infra
tags: [ollama, tenacity, fastapi-dependency-override, protocol, health-check]

# Dependency graph
requires:
  - phase: 05-local-ai-ollama
    plan: "05-01"
    provides: ollama + tenacity runtime deps, ollama Docker service, tunable Ollama Settings fields
provides:
  - LLMProvider Protocol (single complete(prompt, *, json_mode=False) -> str method, D-06)
  - OllamaProvider — tenacity-wrapped ollama.AsyncClient implementation of LLMProvider (D-08)
  - get_llm_provider() DI seam in app/core/dependencies.py — the single override point for tests (D-10)
  - GET /health extended with a non-blocking Ollama reachability probe (degraded-but-200, D-07)
  - FakeLLMProvider + fake_llm_provider/ai_client test fixtures — zero-real-Ollama test infra
affects: [05-03, 05-04, phase-06-rag]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protocol-based provider abstraction (LLMProvider) — first Protocol interface in this codebase; Phase 6's AnthropicProvider implements the same Protocol unchanged"
    - "tenacity @retry decorator scoped to only the network call inside a provider's complete() method, not the whole service method"
    - "get_llm_provider as a bare (non-async) DI function, overridden in tests via app.dependency_overrides — mirrors the existing get_db override pattern"
    - "Degraded-but-200 health check: an optional dependency probe (Ollama) never flips the overall /health status, only its own sub-key"

key-files:
  created:
    - app/ai/__init__.py
    - app/ai/providers/__init__.py
    - app/ai/providers/protocol.py
    - app/ai/providers/ollama.py
    - tests/ai/__init__.py
  modified:
    - app/core/dependencies.py
    - app/api/health.py
    - tests/conftest.py
    - tests/test_health.py

key-decisions:
  - "get_llm_provider is a plain sync function (not async), matching RESEARCH.md's Dependency wiring example verbatim — OllamaProvider construction has no I/O, so no await is needed"
  - "ai_client fixture deletes only the get_llm_provider override key on teardown (not a blanket clear()) — the underlying client fixture already owns get_db and clears everything on its own teardown; deleting a single key first avoids a KeyError race and keeps the two fixtures' responsibilities symmetric"
  - "Health probe imports AsyncClient directly into app/api/health.py module namespace so tests/test_health.py can monkeypatch 'app.api.health.AsyncClient' — no new DI seam introduced for the health probe itself, kept as the plan specified"

patterns-established:
  - "New app/ai/ domain package follows the same providers/ subpackage shape RESEARCH.md and PATTERNS.md prescribed — protocol.py (interface) + ollama.py (concrete impl) — ready for 05-03/05-04 to add router.py/service.py/schemas.py/prompts.py alongside it"

requirements-completed: [AIL-01, AIL-02]

# Metrics
duration: 56min
completed: 2026-07-05
---

# Phase 5 Plan 02: Provider Seam + Health Probe + Wave 0 Test Infra Summary

**LLMProvider Protocol + tenacity-wrapped OllamaProvider behind a single `get_llm_provider` DI seam, `GET /health` now reports Ollama reachability without ever blocking, and a hand-rolled `FakeLLMProvider`/`ai_client` fixture pair gives 05-03/05-04 zero-real-Ollama test coverage.**

## Performance

- **Duration:** 56 min
- **Completed:** 2026-07-05
- **Tasks:** 3 (all auto)
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments
- `app/ai/providers/protocol.py` defines `LLMProvider(Protocol)` with the single `async def complete(prompt, *, json_mode=False) -> str` method (D-06) — the contract both `OllamaProvider` (this phase) and Phase 6's future `AnthropicProvider` implement unchanged
- `app/ai/providers/ollama.py` defines `OllamaProvider`, wrapping `ollama.AsyncClient` with a bounded `tenacity` retry (3 attempts, exponential backoff 1-5s, retrying only `ConnectionError`/`httpx.TimeoutException`/`httpx.ConnectError`, `reraise=True`) — raises only plain library exceptions, never `HTTPException` (D-08)
- `app/core/dependencies.py::get_llm_provider()` constructs `OllamaProvider` from `settings.ollama_*` — the single injectable seam tests override (D-10)
- `GET /health` now probes Ollama with a 2.0s-timeout `AsyncClient.list()` call and returns `{"status": "ok", "ollama": "ok" | "unreachable"}`, staying 200 even when Ollama is down (D-07 degraded-but-200, criterion 1)
- `tests/conftest.py` gained `FakeLLMProvider` (assertable `.calls` list, `should_fail` toggle) plus `fake_llm_provider`/`ai_client` fixtures that override `get_llm_provider` with zero real network calls (D-10, criterion 5 infra); `tests/ai/__init__.py` created as the test package for 05-03/05-04's `test_ai.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Define LLMProvider protocol + OllamaProvider + get_llm_provider seam** — `601ffeb` (feat)
2. **Task 2: Extend GET /health with a non-blocking Ollama probe** — `b450f74` (feat)
3. **Task 3: Wave 0 test infra — FakeLLMProvider + ai_client fixture + tests/ai package** — `10c1563` (test)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS)

## Files Created/Modified
- `app/ai/__init__.py` — package marker for the new `app/ai/` domain
- `app/ai/providers/__init__.py` — package marker for `app/ai/providers/`
- `app/ai/providers/protocol.py` — `LLMProvider(Protocol)` with one `complete()` method
- `app/ai/providers/ollama.py` — `OllamaProvider`, tenacity-wrapped `ollama.AsyncClient`
- `app/core/dependencies.py` — added `get_llm_provider()` + `OllamaProvider`/`LLMProvider` imports
- `app/api/health.py` — added the short-timeout Ollama reachability probe
- `tests/conftest.py` — added `FakeLLMProvider`, `fake_llm_provider`, `ai_client` fixtures; imported `get_llm_provider`
- `tests/test_health.py` — replaced the exact-match `{"status": "ok"}` assertion; added `test_health_reports_ollama_status` (monkeypatch-based)
- `tests/ai/__init__.py` — new test package for upcoming AI feature tests

## Decisions Made
- `get_llm_provider` is a plain synchronous function (matches RESEARCH.md's Dependency wiring example verbatim) — no `async`/`await` needed since constructing `OllamaProvider` performs no I/O.
- `ai_client`'s teardown deletes only the `get_llm_provider` key (`del app.dependency_overrides[get_llm_provider]`) rather than calling `.clear()` — this runs before the underlying `client` fixture's own `.clear()` teardown (pytest tears fixtures down in reverse dependency order), so the two fixtures' cleanup responsibilities stay symmetric and non-conflicting.
- Did NOT add `get_ai_service` yet, per the plan's explicit instruction — `AIService` doesn't exist until 05-03.

## Deviations from Plan

None — plan executed exactly as written. All three tasks matched their `<action>` specs, acceptance criteria, and RESEARCH.md Pattern 1/2 verbatim code.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required. (The one-time `docker compose exec ollama ollama pull llama3.2:3b` step remains from 05-01 and is still deferred to the 05-04 live checkpoint; this plan's health probe and provider seam work correctly against an unreachable/un-pulled Ollama since the tests never hit a real Ollama instance.)

## Next Phase Readiness
- `LLMProvider`/`OllamaProvider`/`get_llm_provider` are ready for 05-03 (`AIService.summarize`) and 05-04 (`AIService.suggest_tags`) to build `app/ai/service.py`/`router.py`/`schemas.py`/`prompts.py` on top of, per RESEARCH.md's `get_ai_service` composition example.
- `FakeLLMProvider` + `ai_client` fixture give 05-03/05-04's `tests/test_ai.py` (in the now-existing `tests/ai/` — note: RESEARCH.md's file map shows `tests/test_ai.py` at the top level, not inside `tests/ai/`; either location works with the `tests/ai/__init__.py` package marker in place for whichever the next plan chooses) a ready-made zero-network override seam.
- `GET /health` truthfully reports Ollama reachability (criterion 1) — no blockers for 05-03/05-04.
- No blockers.

## Self-Check: PASSED

- `app/ai/__init__.py`, `app/ai/providers/__init__.py`, `app/ai/providers/protocol.py`, `app/ai/providers/ollama.py`, `tests/ai/__init__.py` — all present (created).
- `app/core/dependencies.py`, `app/api/health.py`, `tests/conftest.py`, `tests/test_health.py` — all present (modified).
- Commits `601ffeb`, `b450f74`, `10c1563` — all present in git history (`git log --oneline -5`).
- Automated verification: `uv run python -c "from app.ai.providers.protocol import LLMProvider; ... print('ok')"` → `ok`; `uv run ruff check app/ai app/core/dependencies.py` → all checks passed; `uv run pytest tests/test_health.py -q` → 2 passed; `uv run pytest tests/ -q` → 118 passed (no regression).

---
*Phase: 05-local-ai-ollama*
*Completed: 2026-07-05*
