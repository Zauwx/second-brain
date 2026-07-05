# Phase 5: Local AI (Ollama) - Research

**Researched:** 2026-07-05
**Domain:** Local LLM integration (Ollama) in an async FastAPI + SQLAlchemy 2 app, Docker Compose service wiring, provider abstraction, resilience (tenacity/503), fully-mocked LLM testing
**Confidence:** HIGH (core Ollama Python client + Docker Compose resource-limit behavior verified against official GitHub source/docs and PyPI; a few specifics — exact `AsyncClient` timeout kwarg passthrough, small-model structured-output reliability — are MEDIUM and flagged)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Summarization (AIL-01)**
- **D-01:** Synchronous `POST /ai/summarize`. The request blocks until the summary is generated (~5-30s on CPU) and returns it in the response. Simplest to build and demo in Swagger; appropriate for a single-user personal tool. Set a generous request/inference timeout so a valid summary is not cut off. (Background-task/202+poll was offered and rejected as unnecessary complexity for this scale — but note criterion 2 permits either; sync is the chosen path.)
- **D-02:** Persist the summary on the note. Add a nullable `summary` column to the `Note` model via a new Alembic migration (chained from the latest Phase-4 migration). `summarize` writes it; `GET /notes` / `GET /notes/{id}` surface it in the read schema. (Ephemeral return-only was offered and rejected — persistence is more useful and exercises another migration.)
- **D-03:** Model: `llama3.2:3b` for summarization (named in criterion 2). Prompt targets a 2-3 sentence summary.

**Tag Suggestion (AIL-02)**
- **D-04:** `POST /ai/suggest-tags` is suggest-only. It returns a JSON list of proposed tag strings; it does not attach anything. The user then attaches the tags they want via the existing Phase-4 attach endpoint (`POST /notes/{id}/tags` find-or-create). Keeps a human in the loop, matches the "suggest" naming, and avoids the LLM writing directly to the note's tags. (Auto-attach via Phase-4 find-or-create was offered and rejected for this phase.)
- **D-05:** Same model (`llama3.2:3b`) for tagging, prompted to return a JSON list of tag strings. (A second structured-JSON model — qwen2.5:3b per CLAUDE.md — was offered and rejected to keep one model to pull/prebake and lower memory.) Planner should handle lenient parsing of the model's JSON output (strip stray prose, tolerate minor format drift).

**Provider Abstraction**
- **D-06:** Build a thin provider abstraction now. Define an `LLMProvider` protocol/interface with a concrete `OllamaProvider` implementation this phase. Phase 6 adds an `AnthropicProvider` behind the same interface (local/cloud routing). Keep it minimal — one Protocol + one impl — not a speculative framework.

**Resilience / Degradation**
- **D-07:** `503 Service Unavailable` when Ollama is unreachable or errors after retries. AI is an optional enhancement — the core note app keeps working without it. Return a clear message; do not conflate with generic 500s.
- **D-08:** Bounded `tenacity` retry around the Ollama call — a small number of retries with short backoff for transient timeouts / model cold-start, then give up to 503. (CLAUDE.md already prescribes tenacity for LLM calls.)
- **D-09:** Explicit memory limit on the ollama service in `docker-compose.yml` (~4GB starting point; `llama3.2:3b` is ~2GB + inference overhead). Satisfies criterion 4 (verifiable via `docker stats`) and prevents OOM-killing sibling containers on a constrained dev box. Planner tunes the exact value.

**Testing**
- **D-10:** All AI tests use a mock LLM client injected via FastAPI dependency override — zero calls to the real Ollama service in the suite (criterion 5). Cover: successful summarize (persists), suggest-tags (returns list), Ollama-down → 503, retry-then-succeed, and per-user ownership (403/404) on the target note.

### Claude's Discretion (sensible defaults — planner/researcher may refine)
- Exact endpoint URL shape: `/ai/summarize` + `/ai/suggest-tags` taking a note ID in the body/path vs `/notes/{id}/summarize` resource-scoped — planner picks the cleanest; must operate on the caller's own note and honor the Phase-3 404-vs-403 contract.
- Prompt wording for both summarize and tag-suggest, and how strictly to parse/validate the tag JSON.
- Which Ollama Python client / call style (`AsyncClient`) and how the api container discovers the ollama host (service name + port on the Docker network).
- How the `llama3.2:3b` model is provisioned (pull at runtime on first call vs prebaked/entrypoint pull) and how `/health` probes Ollama reachability.
- Exact tenacity retry count/backoff and the request timeout value for the synchronous call.
- Whether the ollama memory limit is expressed via `mem_limit` (Compose v2) or `deploy.resources.limits` — planner's call for the dev Compose file.

### Deferred Ideas (OUT OF SCOPE)
- Background/async summarization (202 + poll) — offered, deferred; sync is fine at this scale (D-01). Revisit only if latency becomes a real UX problem.
- Auto-attaching suggested tags — offered, deferred; suggest-only this phase (D-04). Could become a "one-click apply" enhancement later.
- Second specialized tagging model (qwen2.5:3b for structured JSON) — offered, deferred; one model this phase (D-05). Revisit if `llama3.2:3b` JSON output proves unreliable.
- Cloud LLM (Anthropic), RAG, embeddings, `note_chunks`, related-notes, NL Q&A — Phase 6; the D-06 provider abstraction is built now specifically so Phase 6 slots in cleanly.
- Prebaking the model into a custom Ollama image / GPU acceleration — a prod concern (CLAUDE.md prod variant); dev pulls the model. Fits Phase 7 (prod Compose) rather than here.

None of the above is scope creep into Phase 5 — they are correctly sequenced into their own phases.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIL-01 | User can generate an automatic summary of a note via a local LLM | `POST /ai/summarize` design (Code Examples §OllamaProvider, §AIService.summarize), `Note.summary` migration (§Migration + Schema), 503/retry resilience (§Resilience) |
| AIL-02 | User can get automatically suggested tags for a note via a local LLM | `POST /ai/suggest-tags` design (Code Examples §AIService.suggest_tags), lenient JSON parsing (§Code Examples §_parse_tag_list), reuse of Phase-4 attach endpoint (no new attach logic) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.12 pinned; FastAPI 0.115.x async; Pydantic v2 (`ConfigDict(from_attributes=True)`); SQLAlchemy 2.x async (`DeclarativeBase`, `AsyncSession`) — never sync SQLAlchemy in async routes.
- `asyncmy` only for MySQL (never `aiomysql`); Alembic-only schema management (never `Base.metadata.create_all()`); migrations chain from the current head.
- `tenacity` is the prescribed retry library for LLM calls (Ollama timeouts). `httpx` is available for direct REST calls if the `ollama` client proves insufficient.
- Ollama Python client (`ollama` package) `AsyncClient` is the prescribed local-LLM client — CLAUDE.md names `llama3.2:3b` for summarization/tagging.
- **No LangChain / LlamaIndex** — this is a learning project; hand-roll the provider abstraction and prompt/parse logic.
- Docker: only `api:8000` exposed to host; `mysql` and `ollama` stay on the internal Docker network; use `healthcheck` + `depends_on: condition: service_healthy`.
- Secrets/config via `pydantic-settings` reading `.env` (`extra="ignore"` already tolerates future keys) — never hardcode.
- `structlog` is listed as the project's structured-logging library, but no logging framework is used anywhere in the codebase yet (verified via grep — zero hits for `structlog`/`import logging` in `app/`). Not required to introduce it in this phase to meet AIL-01/AIL-02; flagged as an option, not a blocker.
- Router → Service → Repository, domain-per-folder layering (established in `app/notes/`, `app/tags/`, `app/collections/`, `app/search/`) — the new `app/ai/` package must follow this exactly.

## Summary

Phase 5 adds a fourth Docker service (`ollama`) and a new `app/ai/` domain package that wraps it behind a minimal `LLMProvider` protocol. The `ollama` Python package (verified on PyPI, `ollama/ollama-python` GitHub repo, current version 0.6.2) ships an `AsyncClient` that accepts a `host=` kwarg pointing at the Docker service (`http://ollama:11434`) and exposes `chat()`/`generate()` with a `format` parameter that accepts `"json"` (loose JSON mode) or a JSON schema dict (strict, grammar-constrained decoding via Ollama's structured-outputs feature) — either works for D-05's "JSON list of tag strings" requirement, but D-05 explicitly asks for lenient parsing as a safety net regardless of which mode is used, since `llama3.2:3b` is a small model and format drift is expected.

The two critical Docker Compose facts a planner must get right: (1) `deploy.resources.limits.memory` is a Swarm-only construct and is **silently ignored** by plain `docker compose up` unless `--compatibility` is passed — the correct key for D-09's memory limit under this project's `docker compose up` workflow is the top-level service key `mem_limit: 4g` (confirmed in the current Compose file spec); and (2) the official `ollama/ollama` image has no `curl` binary, so the conventional `curl -f http://localhost:11434/...` healthcheck fails outright — use `ollama list` (the shipped CLI, which itself calls the local API) as the healthcheck command instead.

Resilience follows the existing HTTPException-from-service pattern already used for 404/403 in `NoteService`: wrap the Ollama call with a bounded `tenacity` retry (3 attempts, short exponential backoff, retrying on `ConnectionError`/`httpx.TimeoutException`), and catch the final failure in the AI service layer to raise `HTTPException(503, ...)`. Testing follows the project's existing `app.dependency_overrides` pattern (already used for `get_db` throughout `tests/conftest.py`) — a hand-rolled fake `LLMProvider` (not `unittest.mock`) is injected via a new `get_llm_provider` dependency, giving deterministic, assertable, zero-network tests.

**Primary recommendation:** Add `ollama` + `tenacity` to `pyproject.toml`; add an `ollama` service to `docker-compose.yml` with `mem_limit: 4g` and an `ollama list` healthcheck; build `app/ai/` (router → service → provider) mirroring the existing domain layout exactly; add a nullable `Note.summary` column via migration `0006` chained from `0005_add_collections`; document a one-time manual `docker compose exec ollama ollama pull llama3.2:3b` step for dev (do not auto-pull inside the request path — it would blow the synchronous timeout on a cold start).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ollama inference (summarize, tag-suggest) | API / Backend (`app/ai/providers/ollama.py`) | LLM Container (`ollama` service) | The API container owns the HTTP call and retry/timeout policy; the actual model execution happens in the sibling `ollama` container over the internal Docker network — a classic backend-to-internal-service boundary, not a client-tier concern. |
| Prompt construction + JSON parsing/validation | API / Backend (`app/ai/service.py`) | — | Business logic belongs in the service layer per the established Router→Service→Repository pattern; the provider stays a thin transport wrapper (`complete(prompt) -> str`) so Phase 6's `AnthropicProvider` can slot in without the service layer changing. |
| Summary persistence | Database / Storage (MySQL via `NoteRepository`) | API / Backend (service orchestrates the write) | Same pattern as all other note mutations (create/update/delete) — repository is the only place SQL lives. |
| Ownership / 404-vs-403 enforcement | API / Backend (service layer) | — | Reuses `NoteService.get_or_404_owned` — must not be duplicated or re-implemented in the AI service. |
| Ollama reachability probe (`/health`) | API / Backend (`app/api/health.py`) | LLM Container | The API container performs a short-timeout probe against `ollama:11434`; the ollama container's own healthcheck (`ollama list`) is a separate, Compose-level concern that gates `depends_on: condition: service_healthy`. |
| Memory/OOM guard | LLM Container (`ollama` service in Compose) | — | Enforced at the container-runtime level (`mem_limit`), not in application code — this is infrastructure, not a backend responsibility. |
| Tag attachment (post-suggestion) | API / Backend (existing Phase-4 `app/tags/` endpoint) | — | Explicitly out of scope for `app/ai/` per D-04 — no new tier ownership introduced. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ollama` | 0.6.2 (verified PyPI, released 2026-04-29) `[ASSUMED — package name/version sourced from WebSearch/WebFetch, not Context7; see Package Legitimacy Audit]` | Official Python client for the Ollama REST API; provides `AsyncClient` with `chat`/`generate`/`embed` | Prescribed by CLAUDE.md and `.planning/research/STACK.md`; official `ollama/ollama-python` GitHub repo; wraps `httpx` internally, converts connection failures to a plain `ConnectionError` and HTTP-status failures to `ollama.ResponseError` |
| `tenacity` | 9.1.4 (verified PyPI, released 2026-02-07) `[ASSUMED — see Package Legitimacy Audit]` | Retry/backoff decorator for the Ollama call (D-08) | Prescribed by CLAUDE.md; from Tenacity 8.0+ `@retry` auto-detects `async def` and uses `asyncio.sleep` instead of blocking `time.sleep` — required for a non-blocking retry inside an async FastAPI route |
| `ollama/ollama` (Docker image) | `0.31.1` pinned tag `[CITED: Docker Hub tags page via WebSearch, MEDIUM confidence — verify exact current tag at implementation time]` | The local LLM runtime container | Official image; ships the `ollama` CLI (usable as healthcheck) but **not** `curl` (documented image gap, GitHub issue #9781/#5389) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | 0.28.x (already a dev dependency in `pyproject.toml`) | Fallback direct REST call to Ollama's `/api/*` endpoints, and the exception types (`httpx.TimeoutException`, `httpx.ConnectError`) that `tenacity`'s `retry_if_exception_type` should catch alongside the plain `ConnectionError` the `ollama` client raises | Only if the `ollama` client's abstraction proves insufficient (e.g., raw streaming control) — not needed for the summarize/suggest-tags happy path |
| stdlib `unittest.mock.AsyncMock` | Python 3.12 stdlib | Optional alternative to a hand-rolled fake `LLMProvider` in tests | Use the hand-rolled fake (recommended, see Code Examples) for readability and call-count assertions; `AsyncMock` is a fallback if the team prefers a mocking-library idiom |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `ollama` Python client | Raw `httpx` POST to `http://ollama:11434/api/chat` | More control over streaming, but reimplements what the official client already does (JSON parsing, error typing); no benefit for this phase's scope |
| `format="json"` (loose) | `format=<PydanticModel>.model_json_schema()` (strict, grammar-constrained) | Strict schema gives stronger structural guarantees but adds a Pydantic schema class per prompt; D-05 explicitly asks for lenient parsing regardless, so loose `format="json"` + defensive parsing is simpler and equally safe here — either is acceptable, planner's call |
| Bounded `tenacity` retry | No retry, immediate 503 on first failure | Simpler, but the single most common Ollama failure mode in dev is model cold-start (first inference load can take 10-20s beyond a short connect timeout) — a bare 503 with no retry would make the feature flaky on every fresh container start |
| Hand-rolled fake `LLMProvider` in tests | `unittest.mock.AsyncMock` | The project's existing test suite (`tests/conftest.py`) never uses `unittest.mock`; it uses real fixtures and dependency overrides throughout. A hand-rolled fake matches house style and makes "assert zero real Ollama calls" trivially checkable via a `.calls` list |

**Installation:**
```bash
uv add ollama tenacity
```

**Version verification:** `ollama` and `tenacity` were checked against the PyPI registry (`pip index`/PyPI project pages) and via `slopcheck` (see Package Legitimacy Audit below) rather than `npm view`, since this is a Python project. No Context7 MCP tools were available in this environment (upstream anthropics/claude-code#13898); the CLI fallback (`ctx7`) was also not installed on this machine, so all library-API claims below are sourced from the official GitHub repositories and PyPI/docs.ollama.com pages directly via WebFetch, not Context7.

## Package Legitimacy Audit

Both new packages were checked via `slopcheck` (installed successfully with `uv tool run slopcheck`) directly against PyPI.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `ollama` | PyPI | ~2.5 yrs (first release 2024-01-12; current 0.6.2, 2026-04-29) | Very high (official client for a top-tier OSS LLM runtime; exact weekly count not queried) | `github.com/ollama/ollama-python` (official, backed by Ollama Inc.) | `[OK]` | Approved |
| `tenacity` | PyPI | ~10 yrs (long-established, current 9.1.4, 2026-02-07) | Very high (widely-depended-on retry library across the Python ecosystem) | `github.com/jd/tenacity` | `[OK]` | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Note on provenance tagging: per the package-name provenance rule, both package names were originally sourced from this project's own CLAUDE.md/`.planning/research/STACK.md` (training-data-informed, not Context7) and cross-checked via WebSearch/WebFetch against PyPI and the official GitHub repos — so despite the clean `slopcheck [OK]` verdict and registry existence, they are tagged `[ASSUMED]` in the Standard Stack table above per the strict provenance rule (Context7 was unavailable this session). The planner should gate the `uv add ollama tenacity` step behind a lightweight `checkpoint:human-verify` (a quick glance at the installed version) rather than a hard blocker, since both are already named authoritatively in this project's own CLAUDE.md.

## Architecture Patterns

### System Architecture Diagram

```
HTTP Client (Swagger UI)
    │
    │ POST /ai/summarize {note_id}          POST /ai/suggest-tags {note_id}
    ▼
app/ai/router.py  (APIRouter, prefix "/ai")
    │  Depends(get_current_user) → 401 if missing/invalid token
    │  Depends(get_ai_service)
    ▼
app/ai/service.py :: AIService
    │  1. note = await note_service.get_or_404_owned(note_id, current_user)   ──► 404 / 403
    │  2. prompt = build_summarize_prompt(note.content)  |  build_tag_prompt(note.content)
    │  3. try: raw = await provider.complete(prompt, json_mode=...)
    │         except (ConnectionError, RetryError): raise HTTPException(503)
    │  4a. [summarize] → NoteRepository.set_summary(note, raw.strip()) → persisted
    │  4b. [suggest-tags] → _parse_tag_list(raw) → list[str] (NOT persisted, NOT attached)
    ▼
app/ai/providers/protocol.py :: LLMProvider (Protocol)
    │  complete(prompt: str, *, json_mode: bool = False) -> str
    ▼
app/ai/providers/ollama.py :: OllamaProvider
    │  @retry(bounded, tenacity)
    │  AsyncClient(host=settings.ollama_base_url, timeout=settings.ollama_timeout_seconds)
    │      .chat(model="llama3.2:3b", messages=[...], format="json" if json_mode else "")
    ▼
Docker internal network (backend)
    │  HTTP  http://ollama:11434/api/chat
    ▼
ollama container (ollama/ollama:0.31.1)
    │  mem_limit: 4g  (OOM guard, criterion 4)
    │  healthcheck: CMD ollama list
    │  llama3.2:3b loaded on first inference (or pre-pulled by developer)
    ▼
Response streamed back → AsyncClient collects full message → returned up the chain

Parallel path — Health check:
GET /health → app/api/health.py → short-timeout AsyncClient probe (e.g. client.list())
    → {"status": "ok", "ollama": "ok" | "unreachable"}   (degraded-but-200, D-07 philosophy)
```

### Recommended Project Structure

```
app/
├── ai/
│   ├── __init__.py
│   ├── router.py            # POST /ai/summarize, POST /ai/suggest-tags
│   ├── schemas.py           # SummarizeRequest, SuggestTagsRequest, SuggestTagsResponse
│   ├── service.py           # AIService — prompt building, parsing, 503 translation
│   ├── prompts.py           # SUMMARIZE_PROMPT / TAG_PROMPT templates (pure strings/functions)
│   └── providers/
│       ├── __init__.py
│       ├── protocol.py      # LLMProvider Protocol
│       └── ollama.py        # OllamaProvider (tenacity-wrapped AsyncClient)
├── notes/
│   ├── models.py            # + summary: Mapped[str | None] column
│   ├── schemas.py            # NoteRead + summary: str | None
│   └── repository.py        # + set_summary(note, summary) method
├── core/
│   ├── config.py             # + ollama_base_url, ollama_chat_model, ollama_timeout_seconds, ollama_max_retries
│   └── dependencies.py       # + get_llm_provider, get_ai_service
├── api/
│   └── health.py             # extended to probe Ollama reachability
└── main.py                   # + app.include_router(ai_router, prefix="/ai")

alembic/versions/
└── 0006_add_note_summary.py  # down_revision = "0005_add_collections"

tests/
├── conftest.py               # + FakeLLMProvider fixture, get_llm_provider override
└── test_ai.py                # summarize (persists), suggest-tags (list), 503, retry-then-succeed, ownership
```

### Pattern 1: Thin Provider Protocol (D-06)

**What:** A single-method `Protocol` (`complete(prompt, *, json_mode=False) -> str`) rather than task-specific methods (`summarize()`, `suggest_tags()`) on the provider itself. All prompt construction and output parsing lives in `AIService`, not the provider.

**When to use:** This phase's `OllamaProvider`, and Phase 6's `AnthropicProvider` — both just need to turn a prompt into a text completion; the *meaning* of the prompt (summarize vs. tag vs., later, RAG-answer) is a service-layer concern.

**Why this shape:** Matches `.planning/research/STACK.md`'s "Provider Abstraction Pattern" (`LLMProvider.complete(prompt) -> str`) exactly, and keeps the Protocol trivially satisfiable by a fake in tests (one method to stub, not two-plus).

**Example:**
```python
# app/ai/providers/protocol.py
from typing import Protocol


class LLMProvider(Protocol):
    """Minimal contract for any local or cloud LLM backend (D-06).

    Phase 6 adds AnthropicProvider implementing this same Protocol — no
    changes to AIService or the router are required when that lands.
    """

    async def complete(self, prompt: str, *, json_mode: bool = False) -> str: ...
```

### Pattern 2: Bounded Tenacity Retry Around the Ollama Call (D-08)

**What:** `@retry` wraps only the network call inside `OllamaProvider.complete`, not the whole service method — so retries only apply to transient connectivity/timeout failures, not to (e.g.) a parsing error downstream.

**When to use:** Every `OllamaProvider.complete` invocation.

**Example:**
```python
# app/ai/providers/ollama.py
import httpx
from ollama import AsyncClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class OllamaProvider:
    """LLMProvider implementation backed by a local Ollama server (D-06)."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        # `ollama.AsyncClient.__init__(self, host=None, **kwargs)` forwards
        # extra kwargs to the underlying httpx.AsyncClient — `timeout` is a
        # standard httpx.AsyncClient kwarg [MEDIUM confidence: verified the
        # __init__ signature via the official GitHub source, but did not
        # execute the client to confirm the timeout kwarg is honored end-to-end
        # — verify with a real request during implementation].
        self._client = AsyncClient(host=base_url, timeout=timeout)
        self._model = model

    @retry(
        retry=retry_if_exception_type((ConnectionError, httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        response = await self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            format="json" if json_mode else "",
        )
        return response.message.content
```

Source: method signatures (`AsyncClient.__init__(host=None, **kwargs)`, `chat(..., format: Literal['', 'json'] | JsonSchemaValue)`) verified via the official `ollama/ollama-python` GitHub source (`ollama/_client.py`), `[CITED: github.com/ollama/ollama-python]`. `ConnectionError` on connect failure and `ResponseError` on HTTP-status failure verified via the same source and `docs.ollama.com` structured-outputs page, `[CITED]`.

### Pattern 3: Service Layer Translates Provider Failure to 503 (D-07)

**What:** `AIService` catches `tenacity.RetryError` (raised when all bounded attempts are exhausted and `reraise=False`) or, with `reraise=True` as above, the original `ConnectionError`/`httpx` exception — and converts it to `HTTPException(503)`. This mirrors the existing pattern in `NoteService`/`SearchRepository` where the service layer is the only place `HTTPException` is raised, never the repository/provider.

**Example:**
```python
# app/ai/service.py
from fastapi import HTTPException, status

from app.ai.prompts import build_summarize_prompt, build_tag_prompt
from app.ai.providers.protocol import LLMProvider
from app.auth.models import User
from app.notes.repository import NoteRepository
from app.notes.service import NoteService


class AIService:
    def __init__(self, provider: LLMProvider, note_service: NoteService, note_repo: NoteRepository) -> None:
        self._provider = provider
        self._notes = note_service
        self._note_repo = note_repo

    async def summarize(self, note_id: int, current_user: User) -> "Note":
        note = await self._notes.get_or_404_owned(note_id, current_user)
        raw = await self._safe_complete(build_summarize_prompt(note.content))
        return await self._note_repo.set_summary(note, raw.strip())

    async def suggest_tags(self, note_id: int, current_user: User) -> list[str]:
        note = await self._notes.get_or_404_owned(note_id, current_user)
        raw = await self._safe_complete(build_tag_prompt(note.content), json_mode=True)
        return _parse_tag_list(raw)

    async def _safe_complete(self, prompt: str, *, json_mode: bool = False) -> str:
        try:
            return await self._provider.complete(prompt, json_mode=json_mode)
        except (ConnectionError, TimeoutError, OSError) as exc:
            # tenacity reraise=True surfaces the underlying exception after
            # bounded attempts are exhausted — this is the single place the
            # "Ollama is optional" contract (D-07) is enforced.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Local AI service is currently unavailable. Note operations are unaffected.",
            ) from exc
```

### Pattern 4: Lenient JSON Tag-List Parsing (D-05)

**What:** Even with `format="json"`, a 3B model can wrap the array in an object (`{"tags": [...]}`), add trailing prose, or emit near-JSON. Parse defensively: try direct `json.loads`, fall back to regex-extracting the first `[...]` block, unwrap a single-list-valued dict, coerce/normalize, and default to an empty list rather than raising.

**Example:**
```python
# app/ai/service.py (continued)
import json
import re


def _parse_tag_list(raw: str) -> list[str]:
    data: object
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match is None:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                data = value
                break

    if not isinstance(data, list):
        return []

    return [str(t).strip().lower() for t in data if str(t).strip()]
```

### Anti-Patterns to Avoid

- **Auto-pulling the model inside the request path:** Do not call `AsyncClient.pull()` lazily on first `/ai/summarize` request. A cold `llama3.2:3b` pull is a ~2GB download that can take minutes — far beyond any sane synchronous request timeout (D-01). Document a one-time manual `docker compose exec ollama ollama pull llama3.2:3b` step instead (or a Compose one-shot init container if the planner prefers automation — see Common Pitfalls).
- **`curl`-based healthcheck on the `ollama` service:** The official image does not ship `curl` (GitHub issues #9781, #5389) — this healthcheck will always fail. Use `test: ["CMD", "ollama", "list"]`.
- **`deploy.resources.limits.memory` under plain `docker compose up`:** Silently ignored outside Swarm mode / without `--compatibility`. Use the top-level `mem_limit: 4g` service key (confirmed current in the Compose Spec `services` reference).
- **Duplicating ownership logic in `AIService`:** Do not re-implement 404-vs-403 note lookup. Compose `AIService` with the existing `NoteService.get_or_404_owned` (constructor injection), exactly like `TagService`/`CollectionService` already do with `NoteRepository`.
- **Raising `HTTPException` from the provider or repository:** Keep that exclusively in the service layer (`AIService._safe_complete`, mirroring `NoteService`/`SearchService`) — providers/repositories should raise plain Python/library exceptions only.
- **Real API/network calls in pytest:** Never instantiate `OllamaProvider` in tests. Always override `get_llm_provider` with the fake (D-10, criterion 5).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ollama HTTP protocol (chat/generate wire format, streaming reassembly) | A raw `httpx` client hitting `/api/chat` manually | `ollama` package's `AsyncClient` | Already handles request/response shaping, streaming vs non-streaming, and typed exceptions (`ResponseError`, `ConnectionError`) — reinventing this adds surface area with no benefit for this phase |
| Retry/backoff loop | A hand-written `for attempt in range(3): try/except/sleep` loop | `tenacity` `@retry` decorator | `tenacity` correctly uses `asyncio.sleep` for async callables (8.0+) and composes cleanly with `retry_if_exception_type`; a hand-rolled loop is an easy place to introduce a blocking `time.sleep` that stalls the event loop |
| JSON schema enforcement for LLM output | Custom regex/state-machine parser to force valid JSON out of free text | Ollama's `format="json"` (loose) or `format=<json_schema>` (grammar-constrained, works at the Ollama-server layer independent of model) — combined with the lenient parser in Pattern 4 as defense-in-depth | Ollama already does constrained decoding server-side; hand-rolling a stricter parser without using `format` first is solving the wrong end of the problem |

**Key insight:** The two building blocks this phase needs (an Ollama HTTP client, a retry policy) are both already solved by libraries CLAUDE.md prescribes. The only genuinely custom code this phase should write is (a) the `LLMProvider` Protocol/impl seam, (b) prompt templates, and (c) the lenient tag-list parser — all three are small, domain-specific, and exactly the kind of thing a learning project should hand-roll (per the project's explicit "no LangChain" philosophy).

## Common Pitfalls

### Pitfall 1: Model Not Pulled Before First Request

**What goes wrong:** A fresh `ollama_data` volume has no models. The very first `/ai/summarize` call fails — not with a connectivity error, but with an Ollama "model not found" `ResponseError` (HTTP 404 from Ollama's own API), which the tenacity retry (targeting `ConnectionError`/timeouts) will **not** catch, so it surfaces as an unhandled exception → generic 500, not the intended 503.

**Why it happens:** The `ollama/ollama` image starts the server but does not pre-load any models; `llama3.2:3b` must be explicitly pulled (`ollama pull llama3.2:3b`) at least once per volume.

**How to avoid:** Either (a) document the manual pull step (`docker compose exec ollama ollama pull llama3.2:3b`) as part of the dev setup instructions and treat it as a precondition, verified in the phase's manual test plan; or (b) add `ollama.ResponseError` to the exception types the service layer converts to 503 (not just `ConnectionError`) so a missing-model error also degrades gracefully instead of 500ing. Recommend doing both.

**Warning signs:** First-ever `/ai/summarize` call after `docker compose up --build` (fresh volume) returns 500 instead of a summary or a clean 503.

### Pitfall 2: `curl`-Based Healthcheck Silently Fails Forever

**What goes wrong:** A copy-pasted healthcheck (`test: ["CMD", "curl", "-f", "http://localhost:11434/..."]`) never succeeds because the image has no `curl` binary — the `ollama` service never reports healthy, and if `api` has `depends_on: ollama: condition: service_healthy`, the API container never starts.

**How to avoid:** Use `test: ["CMD", "ollama", "list"]` (the shipped CLI calls the local API internally) — documented as the common community workaround for GitHub issues #9781/#5389.

**Warning signs:** `docker compose ps` shows `ollama` stuck in `starting` or `unhealthy` indefinitely; `docker compose logs ollama` shows the server is actually up and responding to `ollama list` manually inside the container.

### Pitfall 3: `deploy.resources.limits.memory` Doesn't Apply Under Plain `docker compose up`

**What goes wrong:** The planner writes the "textbook" Compose resource-limit block (`deploy: resources: limits: memory: 4G`) copied from a Swarm-oriented example (including this project's own `.planning/research/ARCHITECTURE.md` prod-Compose sample, which uses this exact key). Under plain `docker compose up` (not `docker stack deploy`, no `--compatibility` flag), Compose parses but **ignores** the `deploy` key — no memory limit is actually applied, and criterion 4 ("`docker stats` shows the container staying within its configured memory limit") will falsely appear to pass simply because there is no limit to exceed.

**Why it happens:** `deploy.resources.limits` is part of the Compose Deploy Specification, historically Swarm-oriented; only `docker compose --compatibility up` translates it to the classic `mem_limit`/`cpu_shares` fields.

**How to avoid:** Use the top-level service-level `mem_limit: 4g` key directly in `docker-compose.yml` for the `ollama` service — confirmed as a currently-valid `services:`-level attribute in the Docker Compose file reference, independent of Swarm/compatibility mode.

**Warning signs:** `docker inspect <ollama_container> --format '{{.HostConfig.Memory}}'` returns `0` despite a `deploy.resources.limits.memory` block being present in the compose file.

### Pitfall 4: Synchronous Tenacity Retry Blocking the Event Loop

**What goes wrong:** Using `tenacity.retry` on an `async def` function is safe from Tenacity 8.0+ (auto-detects async and uses `asyncio.sleep`), but a planner unfamiliar with this could accidentally use `time.sleep`-based manual retry logic instead, or pin an older `tenacity` version — either would block the event loop during backoff, stalling all concurrent requests (not just the AI ones) for the retry duration.

**How to avoid:** Use `tenacity>=9.0` (well past the 8.0 async-detection threshold; 9.1.4 is current) and the declarative `@retry(...)` decorator directly on the `async def complete` method — never a manual sleep loop.

**Warning signs:** Other endpoints (note CRUD, tag list) become slow/unresponsive specifically while an `/ai/summarize` retry is in backoff.

### Pitfall 5: CPU Inference Latency Exceeding an Unconfigured Default Timeout

**What goes wrong:** `llama3.2:3b` on CPU (Windows/Docker Desktop dev box, per this project's own `.planning/research/STACK.md`) takes ~5-30s per summarization. If `AsyncClient`'s underlying httpx timeout defaults to something short (httpx's own default is 5s total), the very first real request will time out even with Ollama working correctly, and the bounded tenacity retry (3 attempts × short backoff) will not help because 3× a too-short timeout is still too short.

**How to avoid:** Explicitly set a generous timeout (e.g., 30-45s) via the `timeout` kwarg passed into `AsyncClient(...)` — do not rely on library defaults. Read this from `settings.ollama_timeout_seconds` so it is tunable via env var without a code change.

**Warning signs:** Every `/ai/summarize` call fails with a timeout-shaped exception even when `docker compose exec ollama ollama run llama3.2:3b "hello"` works fine manually.

### Pitfall 6: Ollama Container OOM-Killed Mid-Request

**What goes wrong:** `llama3.2:3b`'s ~2GB weights plus KV-cache overhead for a longer note (full context loaded) can approach or exceed a too-tight memory limit, especially if `OLLAMA_NUM_PARALLEL`/`OLLAMA_MAX_LOADED_MODELS` defaults allow more concurrent model instances than the box can hold. The container gets OOM-killed mid-inference; the client sees a connection reset, which — if the exception type isn't in the tenacity retry list — surfaces as an unhandled error rather than a clean 503.

**How to avoid:** Keep the `mem_limit` at the CLAUDE.md-suggested ~4GB starting point (headroom over the ~2GB model), and additionally set `OLLAMA_NUM_PARALLEL=1` / `OLLAMA_MAX_LOADED_MODELS=1` as environment variables on the `ollama` service to prevent multiple concurrent model loads from compounding memory pressure — relevant even for a single-user app if Swagger sends overlapping requests.

**Warning signs:** `docker compose logs ollama` shows the container restarting; `docker stats` shows memory climbing to the limit right before a restart.

## Code Examples

### Settings additions

```python
# app/core/config.py — additions to the existing Settings class
class Settings(BaseSettings):
    ...
    # Ollama (Phase 5) — .env.example already documents these keys
    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "llama3.2:3b"
    ollama_timeout_seconds: float = 30.0
    ollama_max_retries: int = 3
```

### Dependency wiring

```python
# app/core/dependencies.py — additions
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.protocol import LLMProvider
from app.ai.service import AIService


def get_llm_provider() -> LLMProvider:
    """Construct the OllamaProvider from settings.

    This is the seam tests override via app.dependency_overrides (D-10) —
    zero real Ollama calls happen in pytest because this function is never
    invoked; a fake LLMProvider is substituted instead.
    """
    return OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_chat_model,
        timeout=settings.ollama_timeout_seconds,
    )


async def get_ai_service(
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_llm_provider),
) -> AIService:
    note_repo = NoteRepository(db)
    return AIService(provider, NoteService(note_repo), note_repo)
```

### `NoteRepository.set_summary` (new method)

```python
# app/notes/repository.py — addition
async def set_summary(self, note: Note, summary: str) -> Note:
    """Persist an AI-generated summary on the note (D-02).

    Separate from `update()` because NoteUpdate (client-facing schema) has
    validation rules (e.g. content min_length=1, no explicit-null content)
    that don't apply to this server-side-only write.
    """
    note.summary = summary
    await self._session.commit()
    updated = await self.get_by_id(note.id)
    assert updated is not None
    return updated
```

### Test fixtures — fake `LLMProvider` (D-10)

```python
# tests/conftest.py — additions
from app.ai.providers.protocol import LLMProvider
from app.core.dependencies import get_llm_provider


class FakeLLMProvider:
    """Deterministic LLMProvider stand-in — zero network calls (D-10, criterion 5)."""

    def __init__(self, response: str = '["python", "docker"]', should_fail: bool = False) -> None:
        self.response = response
        self.should_fail = should_fail
        self.calls: list[tuple[str, bool]] = []

    async def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        if self.should_fail:
            raise ConnectionError("mock: ollama unreachable")
        return self.response


@pytest.fixture
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest_asyncio.fixture
async def ai_client(client: httpx.AsyncClient, fake_llm_provider: FakeLLMProvider) -> httpx.AsyncClient:
    """AsyncClient with the real LLMProvider replaced by the deterministic fake."""
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider
    yield client
    del app.dependency_overrides[get_llm_provider]
```

Test asserting zero real calls + correct behavior:

```python
# tests/test_ai.py
async def test_summarize_persists_and_uses_mock_only(
    ai_client, auth_client, fake_llm_provider
):
    fake_llm_provider.response = "This is a concise two-sentence summary."
    note = (await ai_client.post("/notes/", json={"content": "Long note text..."})).json()

    resp = await ai_client.post("/ai/summarize", json={"note_id": note["id"]})

    assert resp.status_code == 200
    assert len(fake_llm_provider.calls) == 1          # exactly one provider call
    assert fake_llm_provider.calls[0][1] is False       # json_mode=False for summarize
    fetched = (await ai_client.get(f"/notes/{note['id']}")).json()
    assert fetched["summary"] == "This is a concise two-sentence summary."


async def test_ollama_down_returns_503(ai_client, fake_llm_provider):
    fake_llm_provider.should_fail = True
    note = (await ai_client.post("/notes/", json={"content": "..."})).json()

    resp = await ai_client.post("/ai/summarize", json={"note_id": note["id"]})

    assert resp.status_code == 503
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Free-text prompting + hope the model returns JSON | `format="json"` (loose) or `format=<json_schema>` (strict, grammar-constrained decoding at the Ollama server layer, model-agnostic) | Ollama structured-outputs feature, announced 2024-12-06 per Ollama's own blog | Meaningfully reduces (but per D-05 does not eliminate) the need for lenient parsing; this project still keeps the lenient parser as defense-in-depth per the locked decision |
| `curl`-based Docker healthchecks for Ollama | `ollama list` CLI-based healthcheck | Ongoing — image has never shipped `curl` (tracked in open GitHub issues #9781, #5389) | Any healthcheck copied from generic web-service examples will silently never pass |

**Deprecated/outdated:** None specific to this phase's stack — `ollama` and `tenacity` are both actively maintained with no announced deprecations affecting the APIs used here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ollama` PyPI package name/version (0.6.2) and `tenacity` version (9.1.4) — sourced via WebSearch/WebFetch to PyPI, not Context7 | Standard Stack | Low — both are already named in this project's own CLAUDE.md/STACK.md and pass `slopcheck [OK]`; worst case is a version-string mismatch, not a wrong/malicious package |
| A2 | `ollama/ollama:0.31.1` is a valid, current Docker Hub tag | Standard Stack | Low-medium — image tags change frequently; planner should re-check `docker pull ollama/ollama:<tag>` at implementation time and fall back to `:latest` pinned by digest if the exact tag has moved on |
| A3 | `AsyncClient(host=..., timeout=...)` forwards `timeout` to the underlying httpx client and is honored per-request | Code Examples §OllamaProvider | Medium — if unhonored, the first cold-inference request could time out at httpx's short default; mitigate by testing a real request against a running Ollama container during implementation before trusting the mocked test suite alone |
| A4 | Grammar-constrained `format=<json_schema>` structured output works reliably with `llama3.2:3b` specifically (not just larger/instruction-tuned models) | Don't Hand-Roll, State of the Art | Low — D-05 already mandates lenient parsing regardless, so even if strict-schema mode behaves unexpectedly on this small model, the fallback parser (Pattern 4) absorbs the risk; not a blocking assumption |
| A5 | `ollama.ResponseError` (not just `ConnectionError`) is the exception type raised for "model not found" — should be added to the 503-translation catch list | Common Pitfalls #1 | Medium — if unverified during implementation, a missing-model error could surface as an unhandled 500 instead of a clean 503; planner should write and run the "model not pulled" test case explicitly against the fake provider (`should_fail` variant) and, if feasible, once against a real un-pulled Ollama instance |

## Open Questions

1. **Does `format=<json_schema>` (strict) meaningfully outperform `format="json"` (loose) + lenient parsing for `llama3.2:3b` specifically, given D-05's explicit tolerance for format drift?**
   - What we know: Ollama's structured-outputs feature is server-side grammar-constrained decoding, documented as model-agnostic in principle.
   - What's unclear: Whether a 3B model's actual output quality (not just JSON-validity) differs meaningfully between the two modes for a "list of 3-6 tag strings" task.
   - Recommendation: Start with `format="json"` (simpler, one line) + the lenient parser; only reach for a Pydantic schema (`format=StringList.model_json_schema()`) if manual testing during implementation shows the loose mode producing unusable output (e.g., tags buried in prose despite `format="json"`).

2. **Should the model-provisioning step (`ollama pull llama3.2:3b`) be automated via a Compose one-shot init service, or documented as a manual step?**
   - What we know: Auto-pulling inside the request path is explicitly wrong (Anti-Patterns); CLAUDE.md's prod guidance is to prebake models into a custom image (deferred to Phase 7).
   - What's unclear: Whether the planner wants a `docker-compose.override.yml` init container (`command: ["sh", "-c", "ollama pull llama3.2:3b"]` on a short-lived container depending on `ollama` being healthy) for a smoother `docker compose up` first-run experience, vs. keeping the dev Compose file minimal and documenting the manual `docker compose exec` step in the README.
   - Recommendation: Document the manual step for this phase (lowest complexity, matches "learning project" ethos of visible steps) and leave the init-container automation as a Phase 7 polish item if desired.

3. **Exact endpoint request-body shape for `/ai/summarize` and `/ai/suggest-tags`.**
   - What we know: ROADMAP.md's success criteria literally say "`POST /ai/summarize` with a note ID" and "`POST /ai/suggest-tags` with a note ID" — implying `/ai/...` paths (not `/notes/{id}/summarize`), with the note ID most likely in a JSON body (`{"note_id": int}`) given the plural "with a note ID" phrasing rather than a URL param.
   - What's unclear: Whether the planner prefers the note ID as a path parameter on the `/ai/...` prefix instead (e.g. `POST /ai/summarize/{note_id}`).
   - Recommendation: Use `POST /ai/summarize` and `POST /ai/suggest-tags`, each taking `{"note_id": int}` in the request body (a small `SummarizeRequest`/`SuggestTagsRequest` Pydantic schema) — matches the literal roadmap wording and keeps both endpoints structurally identical.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Desktop / Docker Engine | Running the whole stack (api + mysql + ollama) | ✓ | Docker 29.4.2, Compose v5.1.3 (checked on this dev machine) | — |
| `ollama/ollama` Docker image | The `ollama` Compose service | Not yet pulled (new to this phase) | Recommend pinning `0.31.1` (current at research time) | Pull at `docker compose up --build` time; no fallback needed, this is the phase's core dependency |
| `llama3.2:3b` model weights (~2GB) | Both `/ai/summarize` and `/ai/suggest-tags` | Not yet pulled (new to this phase) | — | Manual `docker compose exec ollama ollama pull llama3.2:3b` documented as a one-time dev setup step |
| `ollama` PyPI package | `OllamaProvider` | Not yet installed (new dependency) | 0.6.2 | — |
| `tenacity` PyPI package | Retry wrapper (D-08) | Not yet installed (new dependency) | 9.1.4 | — |
| `ctx7` CLI / Context7 MCP | Documentation lookups during this research session | ✗ (neither MCP tools nor `ctx7` CLI present) | — | Used official GitHub source files + PyPI/docs.ollama.com pages directly via WebFetch/WebSearch instead — see Sources |

**Missing dependencies with no fallback:**
- None — all missing items above (Docker image, model weights, two pip packages) are exactly what this phase installs; there is no external blocker.

**Missing dependencies with fallback:**
- Context7/`ctx7` unavailable — used direct WebFetch to official sources instead (see Sources); no impact on research quality, only on citation tier (CITED/MEDIUM instead of a hypothetical Context7 HIGH tier for a couple of claims, flagged in the Assumptions Log).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥ 8.0 + pytest-asyncio ≥ 0.24 (`asyncio_mode = "auto"` in `pyproject.toml`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_ai.py -x` |
| Full suite command | `uv run pytest tests/ --asyncio-mode=auto` (already the default per config; testcontainers spins up a real ephemeral `mysql:8.4`, no real Ollama is ever started) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIL-01 | `POST /ai/summarize` returns + persists a summary via the (mocked) local LLM | integration | `pytest tests/test_ai.py::test_summarize_persists_and_uses_mock_only -x` | ❌ Wave 0 |
| AIL-01 | Ollama unreachable → 503, note CRUD still works | integration | `pytest tests/test_ai.py::test_ollama_down_returns_503 -x` | ❌ Wave 0 |
| AIL-01 | Retry-then-succeed (transient failure recovers within bounded attempts) | integration | `pytest tests/test_ai.py::test_summarize_retries_then_succeeds -x` | ❌ Wave 0 |
| AIL-01 / AIL-02 | Cross-user ownership: user B cannot summarize/suggest-tags on user A's note (403), missing note (404) | integration | `pytest tests/test_ai.py::test_summarize_forbidden_wrong_owner -x` etc. | ❌ Wave 0 |
| AIL-02 | `POST /ai/suggest-tags` returns a JSON list of tag strings, does not attach/persist | integration | `pytest tests/test_ai.py::test_suggest_tags_returns_list_only -x` | ❌ Wave 0 |
| AIL-02 | Lenient parser handles a dict-wrapped or prose-polluted model response | unit | `pytest tests/test_ai.py::test_parse_tag_list_lenient_variants -x` | ❌ Wave 0 |
| criterion 1 | `/health` reports Ollama reachability without blocking on a down Ollama | integration | `pytest tests/test_health.py::test_health_reports_ollama_status -x` | ❌ Wave 0 (no `tests/test_health.py` exists yet) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ai.py -x`
- **Per wave merge:** `uv run pytest tests/ --asyncio-mode=auto`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ai.py` — new file; covers AIL-01, AIL-02 per the map above
- [ ] `tests/test_health.py` — new file (does not currently exist; `app/api/health.py` has no test coverage at all today)
- [ ] `tests/conftest.py` — add `FakeLLMProvider`, `fake_llm_provider` fixture, `ai_client` fixture (override `get_llm_provider`) per Code Examples above
- [ ] Framework install: none — pytest/pytest-asyncio/httpx already present; only the app-level `ollama`/`tenacity` deps are new, not test-framework deps

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (new endpoints) | Reuses existing Phase-3 `get_current_user` Bearer/JWT dependency unchanged — no new auth surface introduced |
| V3 Session Management | No | Same as above — no session/token changes in this phase |
| V4 Access Control | Yes | Reuse `NoteService.get_or_404_owned` (403-if-wrong-owner / 404-if-missing) for both `/ai/summarize` and `/ai/suggest-tags` — the AI endpoints must never accept an implicit "operate on any note" path |
| V5 Input Validation | Yes | Pydantic request schemas (`SummarizeRequest{note_id: int}`) validate the request shape; note content itself is trusted first-party data (the caller's own note) fed into the LLM prompt, and the model's output is defensively parsed (Pattern 4) before being persisted or returned — never `eval`'d or executed |
| V6 Cryptography | No | No new secrets/crypto introduced this phase (Ollama has no auth token in this internal-network-only setup) |

### Known Threat Patterns for this phase's stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Missing ownership check on a new endpoint (repeating Pitfall 13 from `.planning/research/PITFALLS.md`, applied to the new `/ai/*` surface) | Elevation of Privilege | Compose `AIService` with `NoteService.get_or_404_owned` — do not write a separate, possibly-forgetful ownership check |
| Resource exhaustion via repeated long-running inference calls (no rate limit on `/ai/summarize`) | Denial of Service | Acceptable at this project's single-user personal scale (explicitly noted in CONTEXT.md specifics); the bounded tenacity retry + generous-but-finite timeout already caps worst-case per-request cost. No additional rate-limiting is recommended for this phase — flagged here only so the planner consciously accepts the tradeoff rather than missing it |
| Indirect prompt content trust (note content fed directly into the LLM prompt) | Tampering (self-inflicted, single-user) | Out of true scope this phase (no cross-user retrieval exists yet — that's Phase 6's RAG concern per PITFALLS.md Pitfall 8) but cheap to do now: wrap note content in explicit prompt delimiters (see `prompts.py` templates) as a forward-compatible habit before Phase 6 introduces cross-note retrieval |
| Ollama service exposed beyond the internal Docker network | Information Disclosure | Do not add a `ports:` mapping for `ollama` in the base `docker-compose.yml` (only `docker-compose.override.yml` dev convenience, if ever, and even then only bound to `127.0.0.1`) — matches the existing `mysql` service pattern already in this repo |

## Sources

### Primary (HIGH confidence)
- `github.com/ollama/ollama-python` (`ollama/_client.py`, `README.md`) — `AsyncClient.__init__(host=None, **kwargs)` signature, `chat()`/`generate()` `format` parameter type, `ResponseError`/`ConnectionError` exception handling — fetched directly via WebFetch of the raw GitHub source
- `pypi.org/project/ollama/` and `pypi.org/project/tenacity/` — current published versions (0.6.2, 9.1.4) and release dates, confirmed directly via WebFetch
- `docs.docker.com/reference/compose-file/services/` — confirmed `mem_limit` is a currently-valid top-level service attribute in the Compose Spec
- `slopcheck` (local run via `uv tool run slopcheck install ollama tenacity`) — both packages returned `[OK]` against the live PyPI registry
- This project's own `pyproject.toml`, `app/` source tree, `docker-compose.yml`, `.env.example`, `alembic/versions/` (read directly) — exact current dependency versions, existing domain-package conventions, migration chain head (`0005_add_collections`)

### Secondary (MEDIUM confidence)
- `docs.ollama.com/capabilities/structured-outputs` and `ollama.com/blog/structured-outputs` — `format="json"` vs. `format=<schema>` behavior; did not find explicit confirmation of small-model reliability, treated as MEDIUM and covered by the lenient-parsing fallback regardless
- WebSearch cross-referencing Docker community forums/blogs (docker-archive/compose-cli#1523, Docker Community Forums threads, lours.me) — confirmed `deploy.resources.limits` is Swarm/`--compatibility`-only under plain `docker compose up`; multiple independent sources agree
- WebSearch cross-referencing GitHub issues #9781/#5389 (ollama/ollama) and several Compose example repos — confirmed the missing-`curl` image gap and the `ollama list` healthcheck workaround
- WebSearch on Docker Hub tags — `ollama/ollama:0.31.1` as a current pinned tag (verify at implementation time; image tags move fast)
- `ollama.com/library/llama3.2` — `llama3.2:3b` disk size (2.0GB) and context window (128K), consistent with this project's own `.planning/research/STACK.md`

### Tertiary (LOW confidence)
- None — all findings above were cross-verified against at least one official source or this project's own existing codebase/docs; no purely-single-source, unverified claims remain in this document outside what's already flagged in the Assumptions Log

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH for versions/registry legitimacy (verified via PyPI + slopcheck); MEDIUM for the exact Docker image tag (moves frequently) — noted in Assumptions Log
- Architecture: HIGH — directly extends this project's own established, already-implemented Router→Service→Repository pattern (verified by reading `app/notes/`, `app/tags/` source), not a hypothetical pattern
- Pitfalls: HIGH for the two Docker Compose gotchas (mem_limit/deploy, missing curl) — corroborated by multiple independent community sources and Docker's own current spec page; MEDIUM for the small-model structured-output reliability pitfall (no authoritative source directly confirms/denies model-specific behavior)

**Research date:** 2026-07-05
**Valid until:** 2026-08-04 (30 days — Ollama Docker image tags and the `ollama`/`tenacity` PyPI packages move at a moderate pace; re-verify the pinned image tag and package versions if planning is delayed past this window)

---
*Phase: 5-Local AI (Ollama)*
*Research completed: 2026-07-05*
