---
quick_id: 260720-1ng
subsystem: api
tags: [fastapi, ollama, llm, ai, rag, tdd, pytest]

requires:
  - phase: 05-local-ai-ollama
    provides: AIService.suggest_tags, OllamaProvider, _parse_tag_list (05-04)
provides:
  - "Provider seam rename json_mode: bool -> format: str | dict = \"\" (honest transport pass-through)"
  - "TAG_SCHEMA constant + schema-constrained suggest_tags generation"
  - "Structured WARNING on unparseable-but-non-empty model output"
  - "Opt-in live_ollama pytest marker + live regression test against the real stack"
affects: [phase-06-anthropic-provider, phase-05-sign-off]

tech-stack:
  added: []
  patterns:
    - "Provider Protocol format seam: caller owns schema, transport is a dumb pass-through"
    - "live_ollama pytest marker for opt-in real-model regression tests, excluded from default run via addopts"

key-files:
  created:
    - tests/ai/test_live_ollama.py
    - .planning/quick/260720-1ng-fix-suggest-tags-returns-empty-list-repl/deferred-items.md
  modified:
    - app/ai/providers/protocol.py
    - app/ai/providers/ollama.py
    - app/ai/service.py
    - app/ai/prompts.py
    - tests/conftest.py
    - tests/ai/test_summarize.py
    - tests/ai/test_suggest_tags.py
    - pyproject.toml

key-decisions:
  - "TAG_SCHEMA is object-wrapped ({tags: [...]})  not a bare array, matching the empirically-verified 3/3 clean shape"
  - "Parse failure stays lenient (200/[]) but now logs a WARNING with the truncated raw output — silence was the root cause of this defect surviving to a live checkpoint"
  - "Dropped the [\"tag-one\",\"tag-two\"] prompt example entirely — it was actively harmful under both format values tested"

requirements-completed: []

duration: 6min
completed: 2026-07-20
---

# Quick Task 260720-1ng: Fix suggest-tags returns empty list Summary

**Replaced the `json_mode=True` -> `format="json"` provider seam with an explicit JSON schema passed as `format=`, fixing the root cause of `POST /ai/suggest-tags` silently returning `{"tags": []}` against the real llama3.2:3b model.**

## Performance

- **Duration:** ~6 min (RED commit to GREEN commit; live verification followed)
- **Started:** 2026-07-20T01:23:42+02:00
- **Completed:** 2026-07-20 (live verification)
- **Tasks:** 3/3 completed
- **Files modified:** 8 (4 source, 4 test) + 1 new test file + 1 deferred-items log

## Accomplishments

- Root cause fixed: `format="json"` forced llama3.2:3b into free-form object output that mimicked the prompt's own placeholder keys; an explicit JSON schema (`TAG_SCHEMA`) constrains it to `{"tags": [...]}`, which the existing lenient parser already unwraps correctly.
- Provider Protocol seam renamed to be honest about what it does: `format: str | dict = ""` pass-through, caller (AIService) owns the schema — not a bool that can't carry one.
- Parse failures are no longer silent: a structured `logger.warning(...)` fires when parsing yields `[]` from non-empty raw output, while the lenient HTTP 200/`[]` contract is preserved (D-05).
- Closed the structural test blind spot: a new opt-in `live_ollama` pytest marker/test drives the real model through the live API — the exact class of regression (real model behavior under the production flag) that a fully-mocked 128-green suite could never catch.
- Verified live against the actual running stack (not just mocks): non-empty, unprefixed tag list returned; suggest-only (D-04) preserved; summarize path unaffected; default suite stays hermetic.

## Task Commits

1. **Task 1: RED — retarget test suite at `format` seam, add warning + live coverage** - `06e3469` (test)
2. **Task 2: GREEN — replace json_mode with pass-through format, add TAG_SCHEMA + warning** - `6a420e4` (fix)
3. **Task 3: Live verification against the running stack** - no source commit (verification-only; api container rebuilt/restarted, mysql/ollama untouched)

_Note: Task 3 required rebuilding only the `api` service (`docker compose build api && docker compose up -d api`) since no bind-mount/`--reload` override exists in this environment; `mysql` and `ollama` containers were never touched (confirmed unchanged uptime)._

## Files Created/Modified

- `app/ai/providers/protocol.py` - `complete(prompt, *, format: str | dict = "")` contract, docstring explains the pass-through/caller-owns-schema design
- `app/ai/providers/ollama.py` - forwards `format` straight to `AsyncClient.chat`; `cast(Any, format)` at the SDK boundary since the Protocol's `str | dict` is intentionally broader than ollama's `Literal['','json'] | dict | None`; guards `response.message.content` against `None`
- `app/ai/service.py` - `TAG_SCHEMA` constant, `logger = logging.getLogger(__name__)`, `_safe_complete(prompt, *, format=...)`, `suggest_tags` calls with `format=TAG_SCHEMA` and logs a WARNING on unparseable non-empty output
- `app/ai/prompts.py` - `build_tag_prompt` drops the `["tag-one","tag-two"]` example; states the semantic requirement only, since `TAG_SCHEMA` now carries the shape contract
- `tests/conftest.py` - `FakeLLMProvider.complete` retyped to `format: str | dict = ""`, `calls: list[tuple[str, str | dict]]`
- `tests/ai/test_summarize.py` - retry-flaky fake retyped to `format`; assertion updated to `calls[0][1] == ""`
- `tests/ai/test_suggest_tags.py` - assertion pinned to `calls[0][1] == TAG_SCHEMA`; new `test_parse_failure_logs_warning` covers the exact real-world failure payload (`{"tag-one": ..., "tag-two": ...}`) and asserts both the lenient 200/`[]` response and a captured WARNING record
- `tests/ai/test_live_ollama.py` (new) - opt-in `live_ollama`-marked test driving the real model through `http://localhost:8000`: registers a uniquely-suffixed user, creates a substantive note, asserts a non-empty unprefixed tag list, and that `GET /notes/{id}` still shows `tags: []`
- `pyproject.toml` - registers the `live_ollama` marker and excludes it by default via `addopts = "-m 'not live_ollama'"`

## Decisions Made

- **TAG_SCHEMA shape (locked in CONTEXT.md):** object-wrapped (`{"tags": [...]}`), not a bare array — matches the empirically-verified 3/3 clean live-model output and requires no change to the existing `_parse_tag_list` dict-unwrap.
- **Observability, not strictness:** an unparseable-but-non-empty model output logs a WARNING rather than escalating to a 502 — a 3B model occasionally misbehaving in normal operation should degrade gracefully, not break the caller (locked decision, D-05 preserved).
- **Prompt example removed entirely** rather than reworded — the specific literal `["tag-one","tag-two"]` was reproduced as object keys under `format="json"` and as a literal `tag-` prefix under `format=""`; the schema now fully owns the shape contract so the prompt only needs to state 3-5 short lowercase topical tags.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy arg-type error at the `format=` -> `ollama.AsyncClient.chat` boundary**
- **Found during:** Task 2 verification (`uv run mypy app/`)
- **Issue:** The Protocol's `format: str | dict` is intentionally broader than the `ollama` package's `chat(format: Literal['', 'json'] | dict[str, Any] | None)`. Passing the wider type directly failed strict mypy.
- **Fix:** `cast(Any, format)` at the SDK call site in `ollama.py`, with a comment explaining every caller in this codebase only ever passes `""` or a schema dict (never the literal `"json"`).
- **Files modified:** `app/ai/providers/ollama.py`
- **Verification:** `uv run mypy app/` → `Success: no issues found in 47 source files`
- **Committed in:** `6a420e4` (Task 2 commit)

**2. [Rule 1 - Bug] Pre-existing mypy return-type gap in the same function, fixed opportunistically**
- **Found during:** Task 2 verification — confirmed via `git stash`/`git stash pop` that this error (`response.message.content` typed `str | None`, function declared `-> str`) predates this task entirely.
- **Issue:** `response.message.content` can legally be `None` per the `ollama` SDK's type stubs; the function's declared return type is `str`.
- **Fix:** `return response.message.content or ""` — trivial, in the exact function already being modified, and required to satisfy the plan's own "ruff and mypy clean" done criterion for Task 2.
- **Files modified:** `app/ai/providers/ollama.py`
- **Verification:** `uv run mypy app/` clean; full suite still 129 passed.
- **Committed in:** `6a420e4` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1, both scoped to the single function this task already modifies).
**Impact on plan:** Both fixes were necessary to satisfy the plan's own mypy-clean verification gate; no scope creep beyond the file/function already in scope.

### Out-of-scope discovery (logged, not fixed)

`uv run ruff format --check app/ tests/` reports 26 files would be reformatted — confirmed via `git stash`/`git stash pop` to be an entirely pre-existing condition unrelated to this task's changes (reproduces identically on pre-Task-1 HEAD). `uv run ruff check` (lint) passes clean both before and after. Logged to `deferred-items.md` in this quick-task directory per the SCOPE BOUNDARY rule; recommend a dedicated repo-wide reformat quick task reviewed separately from behavior changes.

## Issues Encountered

None beyond the two mypy items above (documented as deviations, not issues — both were auto-fixed inline).

## Live Verification Evidence (Task 3)

Stack was already running (api, mysql, ollama). Only `api` was rebuilt/restarted (`docker compose build api && docker compose up -d api`); `mysql` and `ollama` container uptimes were confirmed unchanged before/after (6h / ~51min respectively — never recreated).

**1. Opt-in live pytest test:**
```
uv run pytest -m live_ollama -v
tests/ai/test_live_ollama.py::test_suggest_tags_live_returns_nonempty_unprefixed_tags PASSED [100%]
1 passed, 129 deselected in 7.92s
```

**2. Manual curl acceptance (single shell invocation, register→login→create→suggest-tags→GET→summarize):**

- `POST /ai/suggest-tags` response:
  ```json
  {"tags":["retrieval-augmented generation","natural language processing","information retrieval"]}
  ```
  → 200, non-empty list of tag strings, **no `tag-` prefix artifact**.

- `GET /notes/4` after suggest-tags:
  ```json
  {"id":4, ..., "summary":null, "tags":[]}
  ```
  → suggest-only (D-04) preserved: no write path, `tags` stays empty.

- `POST /ai/summarize` → HTTP `200` (plain-text path not regressed).

**3. Default hermetic suite after live verification:**
```
uv run pytest tests/ -q
129 passed, 1 deselected in 24.74s
```
Live test remains deselected by default; zero real Ollama calls in the default run (D-10 preserved).

### CONTEXT.md acceptance criteria — all confirmed

| # | Criterion | Result |
|---|-----------|--------|
| 1 | `POST /ai/suggest-tags` returns 200 with a non-empty list of tag strings | PASS — `["retrieval-augmented generation","natural language processing","information retrieval"]` |
| 2 | No tag carries a `tag-` prefix artifact | PASS |
| 3 | Suggest-only preserved (D-04) — note's own `tags` stays empty | PASS — `GET /notes/4` → `tags: []` |
| 4 | `pytest tests/` remains hermetic and green | PASS — 129 passed, 1 deselected |
| 5 | `POST /ai/summarize` still works (plain-text path not regressed) | PASS — HTTP 200 |

## User Setup Required

None — no external service configuration required. The fix lives entirely in application code and the already-running compose stack.

## Next Phase Readiness

- Phase 05's BLOCKING concern in STATE.md (`POST /ai/suggest-tags always returns {"tags": []}`) is now cleared with live evidence attached above — Phase 05 sign-off is unblocked.
- The `live_ollama` marker/test pattern is now available for any future AI-domain regression that the mocked suite is structurally blind to (e.g. a future Phase 6 `AnthropicProvider`).
- Deferred: repo-wide `ruff format` drift (26 files, pre-existing, unrelated to this fix) — tracked in `deferred-items.md`, recommend a separate quick task.

---
*Quick task: 260720-1ng*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`06e3469`, `6a420e4`) verified present in `git log`.
