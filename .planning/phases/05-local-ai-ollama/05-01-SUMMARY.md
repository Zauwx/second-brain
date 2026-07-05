---
phase: 05-local-ai-ollama
plan: 01
subsystem: infra
tags: [ollama, tenacity, docker-compose, pydantic-settings, local-llm]

# Dependency graph
requires:
  - phase: 02-docker-foundation
    provides: docker-compose.yml with mysql + api services, backend network, healthcheck/depends_on pattern
  - phase: 01-repo-foundation
    provides: pydantic-settings Settings class with extra="ignore" tolerating future env keys
provides:
  - Running memory-bounded, internal-only ollama Docker service (mem_limit 4g, ollama-list healthcheck, no host ports)
  - ollama + tenacity Python runtime dependencies in the lockfile, importable in the api container
  - Tunable Ollama Settings fields (base_url, chat_model, timeout_seconds, max_retries) + documented .env.example keys
affects: [05-02, 05-03, 05-04, phase-06-rag]

# Tech tracking
tech-stack:
  added: [ollama==0.6.2, tenacity==9.1.4, "ollama/ollama:0.31.1 Docker image"]
  patterns:
    - "Compose internal-only service: no ports, backend network, healthcheck + depends_on: service_healthy (mirrors mysql)"
    - "Ollama settings via pydantic-settings extra=ignore, no @model_validator (no secret in internal-only setup)"

key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - app/core/config.py
    - .env.example
    - docker-compose.yml

key-decisions:
  - "Used mem_limit: 4g (top-level key) not deploy.resources.limits.memory — plain docker compose up silently ignores the latter (D-09, RESEARCH Pitfall 3)"
  - "Healthcheck test: [CMD, ollama, list] not curl — the ollama/ollama image ships no curl binary (RESEARCH Pitfall 2)"
  - "OLLAMA_NUM_PARALLEL=1 / OLLAMA_MAX_LOADED_MODELS=1 to cap concurrent model loads and prevent OOM compounding (RESEARCH Pitfall 6)"
  - "No @model_validator guard on Ollama settings (unlike jwt_secret_key) — internal-network-only, no secret to protect"

patterns-established:
  - "Internal-only sibling Docker service: copy the mysql block shape (no ports, backend network, healthcheck, depends_on: service_healthy)"
  - "Memory-bounded LLM container via top-level mem_limit key for the docker compose up (non-Swarm) workflow"

requirements-completed: [AIL-01, AIL-02]

# Metrics
duration: 12min
completed: 2026-07-05
---

# Phase 5 Plan 01: Ollama Service + Dependencies Summary

**Memory-bounded, internal-only `ollama` Docker service (4g cap, `ollama list` healthcheck, no host ports) plus the `ollama`+`tenacity` runtime deps and tunable Ollama Settings — the infra half of the local-AI foundation slice.**

## Performance

- **Duration:** ~12 min (excluding the blocking human-verify checkpoint wait)
- **Completed:** 2026-07-05
- **Tasks:** 3 (1 blocking-human checkpoint approved + 2 auto)
- **Files modified:** 5

## Accomplishments
- `uv add ollama tenacity` — `ollama==0.6.2` + `tenacity==9.1.4` resolved into `pyproject.toml`/`uv.lock`, both importable in the api container
- Added a `# Ollama (Phase 5)` settings group (`ollama_base_url`, `ollama_chat_model`, `ollama_timeout_seconds`, `ollama_max_retries`) to `Settings`, all env-overridable and documented in `.env.example`
- Added a fourth Docker service `ollama` modeled on the `mysql` block: `mem_limit: 4g`, `ollama list` healthcheck, `ollama_data` named volume, `OLLAMA_NUM_PARALLEL=1`/`OLLAMA_MAX_LOADED_MODELS=1`, internal `backend` network with NO host port; `api.depends_on` now waits on `ollama: condition: service_healthy`

## Task Commits

Each task was committed atomically:

1. **Task 1: Package legitimacy gate (ollama + tenacity)** — no commit; blocking-human checkpoint (T-05-SC), approved by coordinator after live PyPI verification
2. **Task 2: Install ollama + tenacity, add Ollama settings** — `e3b8a7e` (feat)
3. **Task 3: Add the ollama Docker service** — `ef094c1` (feat)

**Plan metadata:** (final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS)

## Files Created/Modified
- `pyproject.toml` — added `ollama` + `tenacity` to `[project].dependencies`
- `uv.lock` — resolved both packages (ollama 0.6.2, tenacity 9.1.4)
- `app/core/config.py` — new `# Ollama (Phase 5)` field group on `Settings` (no validator — no secret)
- `.env.example` — reworked the Ollama block to Phase 5: base_url, chat_model, timeout_seconds, max_retries (removed the unused Phase-4-era `OLLAMA_EMBED_MODEL` placeholder; embeddings are Phase 6 RAG scope)
- `docker-compose.yml` — new memory-bounded internal-only `ollama` service + `ollama_data` volume + `api` depends_on wiring

## Decisions Made
- **Image tag:** Used `ollama/ollama:0.31.1` exactly as prescribed — verified the tag still exists on Docker Hub (last updated 2026-06-30) before committing, so no substitution was needed.
- Kept the healthcheck timings mirroring the `mysql` block but with a generous `start_period: 60s` (Ollama server startup + first model probe is slower than mysqladmin ping).
- Removed the stale `OLLAMA_EMBED_MODEL=nomic-embed-text` line from `.env.example` — it is not one of this plan's four Settings fields and belongs to Phase 6 (RAG/embeddings), which is out of scope here. The four documented keys now match the `Settings` fields exactly.

## Deviations from Plan

None — plan executed exactly as written. The optional image-tag fallback path (Task 3) was not triggered because `ollama/ollama:0.31.1` verified as a current, valid tag. The only editorial change (dropping the unused `OLLAMA_EMBED_MODEL` placeholder from `.env.example`) is a documentation alignment within the task's stated scope, not a functional deviation.

## Issues Encountered
- `uv add` emitted a benign hardlink warning ("Failed to hardlink files; falling back to full copy") — a cache/target cross-filesystem note on this Windows/Docker Desktop box, not an error; both packages installed cleanly.

## User Setup Required
**One-time manual model pull after the first `docker compose up`** (a fresh `ollama_data` volume has no models). Run once on the Docker host:
```
docker compose exec ollama ollama pull llama3.2:3b
```
This is intentionally NOT auto-pulled inside the request path (a cold ~2GB download would blow the synchronous inference timeout — RESEARCH Anti-Patterns). Model consumption is exercised by plans 05-03/05-04.

## Next Phase Readiness
- The `ollama` container now exists (memory-bounded, internal-only, healthchecked) and gates the `api` start — ready for plan 05-02 to build the `app/ai/` provider seam and for 05-03/05-04 to call it.
- `ollama` + `tenacity` are importable, so `OllamaProvider` (tenacity-wrapped `AsyncClient`) can be written next.
- No blockers. Manual `llama3.2:3b` pull is the only precondition before live AI verification (deferred to the 05-04 live checkpoint per the phase plan).

## Self-Check: PASSED

- `pyproject.toml`, `uv.lock`, `app/core/config.py`, `.env.example`, `docker-compose.yml` — all present and modified.
- Commit `e3b8a7e` (Task 2) and `ef094c1` (Task 3) — both present in git history.
- Automated verification: `settings.ollama_base_url ollama_chat_model` prints `http://ollama:11434 llama3.2:3b`; `import ollama, tenacity` exits 0; compose yaml assertions pass; `docker compose config -q` exits 0.

---
*Phase: 05-local-ai-ollama*
*Completed: 2026-07-05*
