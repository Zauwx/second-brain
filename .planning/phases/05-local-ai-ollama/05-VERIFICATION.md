---
phase: 05-local-ai-ollama
verified: 2026-07-19T23:45:12Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 5: Local AI (Ollama) Verification Report

**Phase Goal:** Ollama runs as a Docker service alongside the API; users can trigger automatic summarization and tag suggestion for any note via a local LLM — no cloud calls, no billing, provably private.
**Verified:** 2026-07-19T23:45:12Z
**Status:** passed
**Re-verification:** No — initial verification

## Method

This verification did not take SUMMARY.md/STATE.md claims on trust. The docker compose stack (api, mysql, ollama with `llama3.2:3b` already pulled) was already running. Against that live stack I independently re-ran a full register → login → create-note → suggest-tags → summarize → GET sequence in a single shell invocation (fresh user/note, never touched by prior sessions), read every modified source file end-to-end, ran the full hermetic pytest suite myself, ran `ruff check`/`ruff format --check`/`mypy` myself, and inspected `docker stats` on the live ollama container. The hard prohibitions (no `docker compose down -v`, no volume prune, no stopping/rebuilding ollama, no mysql volume reset) were respected — D-07 graceful-degradation was therefore verified via the existing automated test suite (which exercises it) plus the STATE.md-documented live evidence from the original checkpoint, not re-triggered live by this verification.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts api+mysql+ollama; `GET /health` confirms ollama reachable on the internal network | ✓ VERIFIED | `docker compose ps` shows all three containers `Up`/`healthy`; `curl -s localhost:8000/health` → `{"status":"ok","ollama":"ok"}` (re-run by this verification, not just quoted from SUMMARY) |
| 2 | `POST /ai/summarize` returns a 2-3 sentence summary via `llama3.2:3b`, not blocked past timeout | ✓ VERIFIED | Fresh live call (user id 6, note id 6, this verification session): returned a 3-sentence accurate summary in ~5s, persisted — confirmed by a subsequent `GET /notes/6` showing the same `summary` text |
| 3 | `POST /ai/suggest-tags` returns a JSON list of suggested tag strings | ✓ VERIFIED | Same fresh live session: `{"tags":["docker","compose","ci pipelines"]}` — non-empty, relevant, no `tag-` prefix artifact; `GET /notes/6` afterward shows `"tags":[]` (suggest-only, D-04, confirmed not just claimed) |
| 4 | `docker stats` shows ollama staying within its configured `mem_limit` during a summarize request | ✓ VERIFIED (see caveat) | `docker stats --no-stream` on the live container: `3.6GiB / 4GiB` (90%), no OOM. Container has been up ~1h serving multiple checkpoint + verification requests; usage has crept from the 2.479GiB peak recorded at the original checkpoint toward the 4g ceiling. It has not been OOM-killed and the criterion ("stays within the limit") literally holds, but the margin is now thin — see Anti-Patterns/Notes below |
| 5 | All pytest LLM tests pass using a mock LLM client; zero real Ollama calls in the suite | ✓ VERIFIED | Ran `uv run pytest tests/ -q` myself: `129 passed, 1 deselected in 24.04s`. The 1 deselected is the opt-in `live_ollama` marker (excluded by `addopts = "-m 'not live_ollama'"` in `pyproject.toml`) — confirmed by reading the marker registration, not just the pass count |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker-compose.yml` (ollama service) | Internal-only, `mem_limit`, healthcheck | ✓ VERIFIED | No `ports:` mapping for ollama (internal-only); `mem_limit: 4g`; healthcheck `["CMD","ollama","list"]` |
| `docker/Dockerfile` | api image can run migrations + starts cleanly | ✓ VERIFIED | Copies `alembic.ini` + `alembic/`, `ENV PATH` includes venv bin — fixed by quick task 260719-snb; `docker compose exec api alembic upgrade head` runs against the live container (confirmed in that quick task's evidence and consistent with the currently-running, already-migrated stack) |
| `app/ai/providers/protocol.py` + `app/ai/providers/ollama.py` | `LLMProvider` Protocol + `OllamaProvider` (tenacity retry) | ✓ VERIFIED | One-method Protocol (`complete(prompt, *, format=...)`); `OllamaProvider` wraps `ollama.AsyncClient` with `@retry(... stop_after_attempt(3), wait_exponential, reraise=True)` on connectivity exceptions only |
| `app/api/health.py` | `/health` probes Ollama reachability | ✓ VERIFIED | `AsyncClient(...).list()` with a 2s timeout; degrades to `"unreachable"` on any exception, overall `status` stays `"ok"` (D-07 degraded-but-200) |
| `app/ai/service.py` | `AIService.summarize` + `AIService.suggest_tags` + `_parse_tag_list` | ✓ VERIFIED | Both methods reuse `NoteService.get_or_404_owned`; `_safe_complete` is the sole `HTTPException(503)` raise site; `suggest_tags` has no repository-write call anywhere in its body (D-04 structurally enforced) |
| `app/ai/router.py` | `POST /ai/summarize`, `POST /ai/suggest-tags` | ✓ VERIFIED | Both registered, both documented with `401/403/404/503` responses tables |
| `tests/ai/test_summarize.py`, `tests/ai/test_suggest_tags.py`, `tests/ai/test_live_ollama.py` | Behavior coverage incl. 503-on-down, ownership, lenient parse | ✓ VERIFIED | 133/135/76 lines respectively; contain real assertions (`assert resp.status_code == 503`, ownership 403/404 cases, `_parse_tag_list` direct unit tests) — not stubs |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/ai/router.py POST /suggest-tags` | `AIService.suggest_tags` | `Depends(get_ai_service)` | ✓ WIRED | Confirmed in router source; `get_ai_service` in `app/core/dependencies.py` composes `OllamaProvider` + `NoteService` + `NoteRepository` |
| `AIService.suggest_tags` | `_parse_tag_list` | direct call, `format=TAG_SCHEMA` | ✓ WIRED | Confirmed live: real model output round-tripped through the parser produced the exact list returned over HTTP |
| `AIService.summarize` | `NoteRepository.set_summary` | persist after `_safe_complete` | ✓ WIRED | Confirmed live: `GET /notes/{id}` after summarize showed the persisted text unchanged across the call boundary |
| `app/api/health.py` | `ollama` service | `AsyncClient(host=settings.ollama_base_url).list()` | ✓ WIRED | Confirmed live: `{"status":"ok","ollama":"ok"}` while the container is healthy; STATE.md records it correctly flipping to `"unreachable"` when stopped during the original checkpoint |
| `docker-compose.yml api` | `docker-compose.yml ollama` | `depends_on: ollama: condition: service_healthy` | ✓ WIRED | Confirmed in compose file; `docker compose ps` shows ollama `healthy` before api reports ollama `ok` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `POST /ai/summarize` response `summary` | `raw` from `_safe_complete` | real `llama3.2:3b` inference over the note's actual content (delimited, truncated at 8000 chars) | Yes — fresh live output was contextually accurate to the specific note content used in this verification, not a static string | ✓ FLOWING |
| `POST /ai/suggest-tags` response `tags` | `_parse_tag_list(raw)` | real `llama3.2:3b` inference with `format=TAG_SCHEMA` | Yes — fresh live output (`["docker","compose","ci pipelines"]`) was topically relevant to the specific note content, not hardcoded/empty | ✓ FLOWING |
| `GET /health` `ollama` field | `ollama_status` | live `AsyncClient.list()` call, not a static value | Yes — confirmed reachable now; STATE.md documents it flipping to `"unreachable"` when the dependency was actually down | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `/health` reports ollama ok | `curl -s localhost:8000/health` | `{"status":"ok","ollama":"ok"}` | ✓ PASS |
| Model present in the running ollama volume | `docker compose exec ollama ollama list` | `llama3.2:3b  2.0 GB` | ✓ PASS |
| suggest-tags is non-empty + relevant + suggest-only on a fresh note | full register→login→create→suggest-tags→GET sequence (this session) | `{"tags":["docker","compose","ci pipelines"]}`; `GET` shows `tags:[]` | ✓ PASS |
| summarize persists an accurate summary on a fresh note | same sequence, `POST /ai/summarize` then `GET` | 3-sentence accurate summary, identical on GET | ✓ PASS |
| Hermetic suite is fully green, real-Ollama test excluded by default | `uv run pytest tests/ -q` | `129 passed, 1 deselected` | ✓ PASS |
| Lint/type gates on phase-5 code | `uv run ruff check app/ai app/api/health.py` / `uv run mypy app/` | both clean | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention exists in this repo and none is declared in the Phase 5 plans/summaries. Step 7c: SKIPPED (no probe scripts; live checkpoint was executed as an interactive `checkpoint:human-verify` gate per 05-04-PLAN.md Task 3, not a probe script).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| AIL-01 | 05-01, 05-02, 05-03 | User can generate an automatic summary of a note via a local LLM | ✓ SATISFIED | `POST /ai/summarize` live-verified this session; persisted; 503-on-down tested |
| AIL-02 | 05-01, 05-02, 05-04 | User can get automatically suggested tags for a note via a local LLM | ✓ SATISFIED | `POST /ai/suggest-tags` live-verified this session (fresh note, non-empty, relevant); suggest-only preserved; fix (260720-1ng) confirmed present in current code (`TAG_SCHEMA`, `format=` seam) |

No orphaned requirements — `.planning/REQUIREMENTS.md` maps exactly AIL-01/AIL-02 to Phase 5, both claimed and both satisfied.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in any phase-5-modified file (`app/ai/*`, `app/api/health.py`, `docker-compose.yml`, `docker/Dockerfile`, `tests/ai/*`) | — | none |
| `app/ai/providers/ollama.py`, `app/core/config.py`, `tests/ai/test_live_ollama.py`, `tests/ai/test_suggest_tags.py`, `tests/ai/test_summarize.py` | — | `ruff format --check` would reformat these 5 files (of a repo-wide 26) | ℹ️ Info | Purely cosmetic formatting drift (quote-style/wrapping), not a lint error — `ruff check` (the actual linter) passes clean and `mypy` passes clean on all of `app/`. Confirmed pre-existing per quick-task 260720-1ng's own `git stash` check and logged to that quick task's `deferred-items.md`. Does not affect behavior. Not a phase-5 blocker, but note that 3 of the 5 drifted files were themselves touched *by* phase-5/its follow-up fix, so "unrelated to this task" is only true in the sense that the drift predates the touch, not that phase-5 work is drift-free |
| `.planning/phases/05-local-ai-ollama/05-04-PLAN.md` (Task 3, `how-to-verify`) | steps 1-7 | Documented live-checkpoint sequence goes straight from `docker compose up -d` to registering a user, with no `alembic upgrade head` step | ⚠️ Warning | On a genuinely fresh MySQL volume this sequence 500s (`Table 'secondbrain.users' doesn't exist`) exactly as it did before quick-task 260719-snb fixed the underlying Dockerfile defect. The Dockerfile bug that made the missing step *fatal* is now fixed (assets are copied, alembic runs), but the plan text itself was never corrected to include the migration step. This is a documentation-accuracy gap, not a code gap — the current running stack IS migrated (confirmed: all endpoints work) — but a fresh clone following 05-04-PLAN.md verbatim would still hit a step no one told them to run. Recorded honestly per the verification brief; does not block phase sign-off since the code artifact (working migrations) exists and is proven, only the plan's prose is stale |
| `app/api/health.py` | 18-24 | `/health` reports `ollama: "ok"` based on reachability (`client.list()` succeeding) only — it does not check whether `llama3.2:3b` specifically is present | ℹ️ Info | Documented, known, already-discovered-during-the-phase limitation (STATE.md Blockers/Concerns). Criterion 1's literal wording ("`GET /health` confirms ollama is reachable") is satisfied by the current implementation — it is a reachability probe, and it is one. The gap is a UX/observability sharp edge (green health while every AI call 503s if the model isn't pulled yet), not a criterion-1 failure. Recorded here for visibility; recommend a follow-up quick task or Phase 6 note, not a Phase 5 blocker |

## Human Verification Required

None. All five ROADMAP success criteria were independently re-verified against the live running stack by this verification pass (fresh HTTP calls, fresh test run, fresh lint/type run, fresh `docker stats` read) rather than accepted from SUMMARY.md/STATE.md narrative. No item requires visual/subjective human judgment beyond what has already been confirmed programmatically.

## Gaps Summary

No blocking gaps. All 5 ROADMAP success criteria for Phase 5 hold, verified independently and freshly (not merely re-stated from prior claims):

1. Ollama Docker service reachable via `/health` on the internal network.
2. `POST /ai/summarize` produces and persists an accurate 2-3 sentence summary via `llama3.2:3b`.
3. `POST /ai/suggest-tags` returns a non-empty, relevant JSON tag list, suggest-only — the empty-list defect found during the original live checkpoint (json_mode → bare "json" format) is confirmed fixed in the current code (`TAG_SCHEMA` + `format=` pass-through seam) and reproducibly correct on a brand-new note in this verification session.
4. Ollama stays within its `mem_limit: 4g` — no OOM observed, though current idle usage (3.6GiB/4GiB, ~90%) after ~1h of cumulative checkpoint+verification traffic is closer to the ceiling than the 2.479GiB peak recorded at the original checkpoint. Worth a human decision on whether to raise the limit or investigate for a slow leak before heavy Phase-6 RAG traffic — flagged as an observation, not a phase-5 failure, since the criterion as literally worded ("stays within its configured memory limit") holds.
5. Full hermetic pytest suite (129 tests) is green with zero real-Ollama calls; the one real-model regression test added by the 260720-1ng fix is correctly excluded from the default run via an opt-in marker.

Two documentation-accuracy items are recorded honestly above (missing `alembic upgrade head` step in 05-04-PLAN.md's checkpoint instructions; the pre-existing repo-wide `ruff format` drift touching a few phase-5 files) — neither blocks the phase goal, since the underlying code artifacts they'd describe (working migrations, passing lint) are independently confirmed working.

---

*Verified: 2026-07-19T23:45:12Z*
*Verifier: Claude (gsd-verifier)*
