# Phase 5: Local AI (Ollama) - Context

**Gathered:** 2026-07-05
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **local-LLM enhancement layer** on top of the existing Note CRUD + organization API: Ollama runs as a Docker service on the internal network, and users can trigger **automatic summarization** and **automatic tag suggestion** for one of their own notes via a local model — no cloud calls, no billing, provably private.

In scope:
- **Ollama as a Docker service** — added to `docker-compose.yml` on the internal network (not exposed to host); the api container reaches it over the Docker network; `GET /health` confirms reachability (criterion 1).
- **`POST /ai/summarize`** — synchronous; generates a 2-3 sentence summary of a note via `llama3.2:3b` and **persists it** on the note (AIL-01, criterion 2).
- **`POST /ai/suggest-tags`** — returns a JSON list of suggested tag strings from the local LLM (suggest-only; user attaches chosen tags via existing Phase-4 endpoints) (AIL-02, criterion 3).
- **Thin LLM provider abstraction** — `LLMProvider` protocol + `OllamaProvider` implementation, so Phase 6 can slot in a cloud provider without reworking the AI service layer (phase goal: "LLM provider abstraction").
- **Resilience** — 503 when Ollama is unavailable, bounded `tenacity` retry for transient/cold-start timeouts, and an explicit **memory limit** on the ollama service (OOM guard, criterion 4).
- **Fully-mocked LLM tests** — all pytest AI tests use a mock LLM client; zero calls to the real Ollama service (criterion 5).

Maps to requirements: **AIL-01, AIL-02**.

Out of scope (later phases / deferred): RAG, embeddings, `note_chunks`, semantic/related-notes search, natural-language Q&A, and any cloud LLM (Anthropic) — all Phase 6. CI/CD + prod Compose + versioned images — Phase 7. Explicitly deferred this phase: background/async summarization jobs, auto-attaching suggested tags, a second specialized tagging model.

</domain>

<decisions>
## Implementation Decisions

### Summarization (AIL-01)
- **D-01:** **Synchronous `POST /ai/summarize`.** The request blocks until the summary is generated (~5-30s on CPU) and returns it in the response. Simplest to build and demo in Swagger; appropriate for a single-user personal tool. Set a generous request/inference timeout so a valid summary is not cut off. (Background-task/202+poll was offered and rejected as unnecessary complexity for this scale — but note criterion 2 permits either; sync is the chosen path.)
- **D-02:** **Persist the summary on the note.** Add a **nullable `summary` column** to the `Note` model via a new Alembic migration (chained from the latest Phase-4 migration). `summarize` writes it; `GET /notes` / `GET /notes/{id}` surface it in the read schema. (Ephemeral return-only was offered and rejected — persistence is more useful and exercises another migration.)
- **D-03:** **Model: `llama3.2:3b`** for summarization (named in criterion 2). Prompt targets a 2-3 sentence summary.

### Tag Suggestion (AIL-02)
- **D-04:** **`POST /ai/suggest-tags` is suggest-only.** It returns a JSON list of proposed tag strings; it does **not** attach anything. The user then attaches the tags they want via the **existing Phase-4 attach endpoint** (`POST /notes/{id}/tags` find-or-create). Keeps a human in the loop, matches the "suggest" naming, and avoids the LLM writing directly to the note's tags. (Auto-attach via Phase-4 find-or-create was offered and rejected for this phase.)
- **D-05:** **Same model (`llama3.2:3b`) for tagging**, prompted to return a JSON list of tag strings. (A second structured-JSON model — qwen2.5:3b per CLAUDE.md — was offered and rejected to keep one model to pull/prebake and lower memory.) Planner should handle lenient parsing of the model's JSON output (strip stray prose, tolerate minor format drift).

### Provider Abstraction
- **D-06:** **Build a thin provider abstraction now.** Define an `LLMProvider` protocol/interface with a concrete `OllamaProvider` implementation this phase. Phase 6 adds an `AnthropicProvider` behind the same interface (local/cloud routing). Keep it minimal — one Protocol + one impl — not a speculative framework. (In-scope per the phase goal "LLM provider abstraction".)

### Resilience / Degradation
- **D-07:** **`503 Service Unavailable`** when Ollama is unreachable or errors after retries. AI is an optional enhancement — the core note app keeps working without it. Return a clear message; do not conflate with generic 500s.
- **D-08:** **Bounded `tenacity` retry** around the Ollama call — a small number of retries with short backoff for transient timeouts / model cold-start, then give up to 503. (CLAUDE.md already prescribes tenacity for LLM calls.)
- **D-09:** **Explicit memory limit on the ollama service** in `docker-compose.yml` (~4GB starting point; `llama3.2:3b` is ~2GB + inference overhead). Satisfies criterion 4 (verifiable via `docker stats`) and prevents OOM-killing sibling containers on a constrained dev box. Planner tunes the exact value.

### Testing
- **D-10:** **All AI tests use a mock LLM client** injected via FastAPI dependency override — zero calls to the real Ollama service in the suite (criterion 5). Cover: successful summarize (persists), suggest-tags (returns list), Ollama-down → 503, retry-then-succeed, and per-user ownership (403/404) on the target note.

### Claude's Discretion (sensible defaults — planner/researcher may refine)
- Exact endpoint URL shape: `/ai/summarize` + `/ai/suggest-tags` taking a note ID in the body/path vs `/notes/{id}/summarize` resource-scoped — planner picks the cleanest; must operate on the caller's own note and honor the Phase-3 404-vs-403 contract.
- Prompt wording for both summarize and tag-suggest, and how strictly to parse/validate the tag JSON.
- Which Ollama Python client / call style (`AsyncClient`) and how the api container discovers the ollama host (service name + port on the Docker network).
- How the `llama3.2:3b` model is provisioned (pull at runtime on first call vs prebaked/entrypoint pull) and how `/health` probes Ollama reachability.
- Exact tenacity retry count/backoff and the request timeout value for the synchronous call.
- Whether the ollama memory limit is expressed via `mem_limit` (Compose v2) or `deploy.resources.limits` — planner's call for the dev Compose file.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — product context; the IA-hybride goal (local Ollama for résumé/tagging, cloud later for RAG) and the "learn to route local vs cloud" objective directly motivate this phase and the D-06 provider abstraction.
- `.planning/REQUIREMENTS.md` — **AIL-01** (local summary) and **AIL-02** (local suggested tags) are the requirements in scope; RAG-01/RAG-02 are the Phase-6 siblings that will reuse the provider abstraction.
- `.planning/ROADMAP.md` §"Phase 5: Local AI (Ollama)" — the 5 success criteria this phase is judged against (ollama reachable via /health; /ai/summarize non-blocking-to-timeout via llama3.2:3b; /ai/suggest-tags JSON list; ollama within memory limit; all LLM tests mocked).
- `.planning/STATE.md` §Decisions — canonical pagination envelope, testcontainers strategy, Alembic-not-create_all, per-user isolation contract.

### Stack / framework guidance (in CLAUDE.md)
- `CLAUDE.md` §"Local LLM: Ollama Models and Client" — `llama3.2:3b` (~2GB, summarization), Ollama exposes an OpenAI-compatible REST API, use the `ollama` Python client / `AsyncClient` for async usage.
- `CLAUDE.md` §"Provider Abstraction Pattern" — the intended shape for D-06.
- `CLAUDE.md` §"Docker: Service Architecture" — expose only api:8000 to host; mysql/ollama/qdrant stay on the internal network; healthcheck + depends_on; Ollama on CPU is slow in dev (5-30s per 3B summarization); pre-bake models for prod.
- `CLAUDE.md` supporting libs — **tenacity** (retry for Ollama timeouts, D-08), **httpx** (can call Ollama REST directly if needed), **structlog** for logging.
- `.planning/research/STACK.md` — async patterns, pytest-asyncio + httpx AsyncClient testing, dependency-override mocking.
- `.planning/research/ARCHITECTURE.md` — domain-per-folder layering (Router → Service → Repository) to mirror for the new `app/ai/` package.

### Prior phase carry-forward (integration foundation)
- `.planning/phases/04-tags-collections-full-text-search/04-CONTEXT.md` — Phase-4 tag **find-or-create (normalized, per-user)** attach endpoint that users call to attach suggested tags (D-04); `NoteRead` schema shape to extend with `summary`.
- `.planning/phases/03-auth-per-user-data-isolation/03-CONTEXT.md` — per-user scoping + 403/404 ownership contract the AI endpoints MUST inherit (operate only on the caller's own note).
- `.planning/phases/02-database-api-skeleton/02-CONTEXT.md` — pagination envelope, Alembic-migrations-only, testcontainers MySQL harness.

### Existing code (integration targets)
- `app/notes/models.py` — `Note` model; add the nullable `summary` column here (D-02).
- `app/notes/schemas.py` — `NoteRead`; surface the new `summary` field.
- `app/notes/service.py` / `repository.py` — reuse `get_or_404_owned` / ownership pattern so AI endpoints resolve the caller's note with 404-vs-403; repository is where the summary write persists.
- `app/tags/router.py` / `service.py` — the existing attach (`POST /notes/{id}/tags`, find-or-create) endpoint users call to apply suggested tags (D-04).
- `app/core/config.py` — `Settings` with `extra="ignore"` (already tolerates future Ollama env vars); add Ollama host/model/timeout settings here.
- `app/core/dependencies.py` — `get_current_user`, `get_db`; add `get_llm_provider` / `get_ai_service` providers (and the mock override point for tests, D-10).
- `app/main.py` — register the new `ai` router.
- `app/api/health.py` — extend `/health` to probe Ollama reachability (criterion 1).
- `docker-compose.yml` — `mysql` + `api` services today; add an `ollama` service on the internal network with a memory limit (D-09); wire `depends_on`/healthcheck.
- `alembic/versions/` — latest Phase-4 migration is the `down_revision` for the new `Note.summary` migration.
- `tests/conftest.py` — testcontainers MySQL harness + dependency-override pattern; add the mock LLM provider fixture (D-10).

No user-referenced external docs/ADRs were introduced during discussion — guidance lives in CLAUDE.md and `.planning/research/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/notes/` (and `app/tags/`, `app/collections/`) packages** are the exact template for a new **`app/ai/`** package (router / schemas / service, plus a `providers/` module for the LLM abstraction) — domain-per-folder is established.
- **`NoteService.get_or_404_owned` + repository `get_by_id`** — the 404-vs-403 ownership pattern to resolve the target note for both AI endpoints.
- **Phase-4 tag attach (find-or-create, normalized, per-user)** — the endpoint users call to apply suggested tags (D-04); no new attach logic needed this phase.
- **`Settings` (`app/core/config.py`, `extra="ignore"`)** — already forward-compatible with new Ollama env vars; extend it, don't restructure.
- **`tests/conftest.py`** testcontainers MySQL + dependency-override — extend with a mock LLM provider fixture so zero real Ollama calls happen (D-10).
- **FastAPI dependency-override** — the mechanism to inject the mock LLMProvider in tests.

### Established Patterns
- **Router → Service → Repository**, zero business logic in routers; the LLM call lives behind the provider abstraction, invoked from the AI service.
- **Alembic migrations, never `Base.metadata.create_all()`** — the `Note.summary` column ships via a new migration chained from the latest Phase-4 migration.
- **Per-user isolation (Phase 3):** AI endpoints operate only on the caller's own note; 404-if-missing / 403-if-wrong-owner.
- **Async throughout** — async SQLAlchemy + an async Ollama client (`AsyncClient`) so inference doesn't block the event loop.
- **Docker internal network** — new `ollama` service is NOT exposed to the host; only `api:8000` is (CLAUDE.md Docker architecture).

### Integration Points
- `docker-compose.yml` gains an `ollama` service (internal network, memory limit, healthcheck); `api` gets `depends_on` + Ollama connection env vars.
- `app/api/health.py` `/health` extends to report Ollama reachability.
- `app/notes/models.py` + `schemas.py` gain the `summary` field; a new Alembic migration adds the column.
- `app/main.py` registers the new `ai` router.
- `app/core/config.py` + `dependencies.py` gain Ollama settings and the `get_llm_provider` / `get_ai_service` providers (with a test override seam).

</code_context>

<specifics>
## Specific Ideas

- This is a **learning project**, and this phase is the first taste of the AI stack: keep the provider abstraction small and legible (Protocol + one impl) so the local↔cloud routing concept is visible, not buried in a framework. No LangChain (CLAUDE.md: hand-rolled).
- The end-to-end demo must work via Swagger: create a note → `POST /ai/summarize` returns and stores a 2-3 sentence summary (visible on `GET /notes/{id}`) → `POST /ai/suggest-tags` returns a JSON list → attach chosen tags via the Phase-4 endpoint → stop Ollama and confirm the endpoints return a clean 503 while note CRUD still works.
- Privacy is a selling point: no cloud calls in this phase — summarization and tagging are provably local (portfolio narrative).
- The 5-30s CPU inference latency is expected and acceptable for a personal single-user tool (D-01 sync choice) — don't over-engineer around it this phase.

</specifics>

<deferred>
## Deferred Ideas

- **Background/async summarization (202 + poll)** — offered, deferred; sync is fine at this scale (D-01). Revisit only if latency becomes a real UX problem.
- **Auto-attaching suggested tags** — offered, deferred; suggest-only this phase (D-04). Could become a "one-click apply" enhancement later.
- **Second specialized tagging model (qwen2.5:3b for structured JSON)** — offered, deferred; one model this phase (D-05). Revisit if `llama3.2:3b` JSON output proves unreliable.
- **Cloud LLM (Anthropic), RAG, embeddings, `note_chunks`, related-notes, NL Q&A** — Phase 6; the D-06 provider abstraction is built now specifically so Phase 6 slots in cleanly.
- **Prebaking the model into a custom Ollama image / GPU acceleration** — a prod concern (CLAUDE.md prod variant); dev pulls the model. Fits Phase 7 (prod Compose) rather than here.

None of the above is scope creep into Phase 5 — they are correctly sequenced into their own phases.

</deferred>

---

*Phase: 5-Local AI (Ollama)*
*Context gathered: 2026-07-05*
