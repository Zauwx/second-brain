# Project Research Summary

**Project:** Second Brain — Personal Knowledge Base with AI
**Domain:** Self-hosted REST API, personal knowledge management, hybrid local + cloud LLM, RAG pipeline
**Researched:** 2026-06-23
**Confidence:** HIGH

---

## Executive Summary

This is an API-first personal knowledge base built with FastAPI + MySQL + Ollama + cloud LLM (Claude), containerized entirely with Docker Compose and hosted on a Windows 11 home lab. The product's core value — saving notes and querying them in natural language — maps directly to a well-understood architecture: relational storage (MySQL), a layered FastAPI service (Router -> Service -> Repository), and a RAG pipeline using local embeddings (nomic-embed-text via Ollama) plus a cloud LLM for answer generation. This is simultaneously a portfolio-quality learning project and a usable daily tool. Every phase delivers a shippable artifact that teaches a specific skill cluster (MySQL/ORM, HTTP/auth, local LLM, RAG, CI/CD).

The recommended build order is strictly sequential: database + CRUD skeleton -> auth + data isolation -> tags/collections/full-text search -> local LLM (Ollama) -> RAG pipeline -> CI/CD hardening. Dependencies are hard: auth must exist before any other feature is meaningful; the embedding infrastructure must exist before RAG Q&A or related-notes can be built. The biggest architectural decision — where to store vector embeddings — has been explicitly resolved (see reconciliation below). There is no justification for adding a dedicated vector DB to this project at personal scale; MySQL JSON columns with in-Python cosine similarity are correct for the starting point, with a clear upgrade path documented for when chunk count exceeds ~50k rows.

The dominant risks are not conceptual but operational: wrong async patterns on day one (sync SQLAlchemy in async FastAPI routes) silently destroy performance and are expensive to retrofit; missing user isolation in queries is a data-leak bug disguised as a routine query; and the RAG phase concentrates the largest cluster of independent pitfalls (chunking, staleness, relevance threshold, prompt injection, cost blowup). All three risk areas have clear mitigations and must be addressed in the phase where they first appear, not retrofitted.

---

## Resolved Disagreement: Vector Store / Embeddings

The four research files disagreed on vector storage approach. This is the explicit reconciliation.

### The Disagreement

| Research File | Recommendation |
|---------------|----------------|
| STACK.md | Qdrant (qdrant-client) as a separate Docker service |
| FEATURES.md | ChromaDB as a sidecar container |
| ARCHITECTURE.md | Embeddings as JSON columns in MySQL; brute-force cosine similarity in Python |
| PITFALLS.md | Warns against MySQL JSON blobs for vectors AND mentions MySQL 9.0+ native VECTOR type |

### Recommendation: MySQL JSON Columns, Upgrade Path Documented

**Primary path: MySQL JSON column (`note_chunks.embedding JSON NOT NULL`)**

For this learning project at personal scale (single user, realistic ceiling of 5,000-20,000 note chunks), MySQL JSON column storage with in-Python cosine similarity is the correct starting architecture. The rationale:

- **Simplicity:** No additional Docker service. The Docker Compose file stays at three services (api, mysql, ollama). Adding Qdrant or ChromaDB adds a fourth service with its own volume, health check, and failure mode before the developer has built a single working feature.
- **Learning value:** The developer explicitly needs to learn MySQL. Implementing chunk storage, querying with JOIN, and computing cosine similarity in Python teaches more about the domain than delegating to a vector DB. The concept of "vector similarity search" is clearer when you write it once by hand.
- **Operational cost:** Zero. No extra RAM for a Qdrant or ChromaDB container on a home lab machine that also runs Ollama (which is memory-hungry).
- **Docker footprint:** Three services instead of four. On Windows Docker Desktop with limited resources, every container counts.
- **Sufficient for the use case:** At < 20k chunks, a Python cosine similarity loop over rows pre-filtered by `WHERE notes.user_id = :user_id` takes well under 100ms. The bottleneck will be Ollama inference, not vector search.

**Upgrade path (flag for RAG phase planning):**

When chunk count approaches 50k rows, or if the project grows beyond self-hosted single-user use:

1. **MySQL 9.0+ native VECTOR type:** If the MySQL image is pinned to 9.0+, the `embedding` column can be migrated from JSON to `VECTOR(768)` and a native ANN index added — zero new services. PITFALLS.md correctly flags this: verify the MySQL image version before choosing this path. `mysql:8.4` (the pinned version in STACK.md and ARCHITECTURE.md) does NOT have this — it requires upgrading to `mysql:9.0+`.
2. **Qdrant sidecar:** Add `qdrant/qdrant:latest` to Docker Compose, migrate the embedding service to use `AsyncQdrantClient`. STACK.md's code patterns are correct and ready to use. This is the right choice if the project adds multiple users or grows to a VPS deployment.
3. **ChromaDB:** Acceptable alternative to Qdrant for single-user; simpler client API but weaker production story (no async client, harder to filter by `user_id` metadata at scale).

**Decision to confirm during RAG phase planning:** Before writing the first embed call, confirm whether `mysql:8.4` will be kept or upgraded to `9.0+`. This determines whether the JSON-to-VECTOR migration path is viable or whether Qdrant should be introduced from the start of the RAG phase.

### Embedding Model: Single Recommended Default

All four research files agree on `nomic-embed-text` via Ollama. The divergence was only in where to store the output, not in how to generate it.

**Recommendation: `nomic-embed-text` via Ollama as the default, with a config-switch escape hatch.**

- **Default:** `EMBEDDING_PROVIDER=ollama` calls `http://ollama:11434/api/embeddings` with model `nomic-embed-text` (274 MB, 768-dim vectors, runs on CPU)
- **Escape hatch:** `EMBEDDING_PROVIDER=openai` calls OpenAI `text-embedding-3-small` API. Add this env var to `pydantic-settings` from day one so the switch requires zero code change.
- **Why not `sentence-transformers` in the API container:** Brings PyTorch (~2 GB) into the FastAPI image. Ollama already runs as a container; adding a model to it is free.
- **Dimension constraint:** `nomic-embed-text` produces 768-dim vectors. If the escape hatch is used with a different model (e.g., OpenAI `text-embedding-3-small` = 1536-dim), existing embeddings become incompatible and must be re-indexed. Document this in a comment at the embed service level.

---

## Key Findings

### Recommended Stack

The stack is narrow and well-justified. Python 3.12 is the correct pin — 3.13 breaks `passlib` (which is itself deprecated; use `pwdlib[argon2]` instead). FastAPI 0.115.x with Pydantic v2 and SQLAlchemy 2.x async is the current standard for this class of application. The three unavoidable library traps — `passlib` (broken), `python-jose` (abandoned), `aiomysql` (unmaintained) — all have direct replacements (`pwdlib`, `PyJWT`, `asyncmy`) that must be in place from Phase 1. Package management via `uv` is correct for 2026; `pip + requirements.txt` is obsolete for new projects.

**Core technologies:**
- **Python 3.12:** pin to 3.12 in Dockerfiles; 3.13 removes the `crypt` module (breaks passlib; use pwdlib instead, but stay on 3.12 for ecosystem stability)
- **FastAPI 0.115.x:** async REST, auto-generates OpenAPI/Swagger, first-class Pydantic v2
- **SQLAlchemy 2.x + asyncmy:** async ORM; `asyncmy` is the only actively maintained async MySQL driver (`aiomysql` unmaintained since 2021)
- **Alembic 1.14.x:** database migrations; wire from Phase 1, never use `create_all()` in production
- **MySQL 8.4:** relational store; pin to minor version; configure `utf8mb4` before creating any table
- **Ollama (latest):** local LLM runtime; `llama3.2:3b` for summarization/tagging, `nomic-embed-text` for embeddings
- **anthropic 0.50.x:** cloud LLM SDK; use `AsyncAnthropic`; default model `claude-sonnet-4-5`
- **PyJWT 2.x + pwdlib[argon2]:** JWT auth and password hashing; both are the current FastAPI-endorsed defaults replacing unmaintained alternatives
- **uv:** package manager; replaces pip + virtualenv; use in Dockerfiles too
- **ruff + mypy + pytest-asyncio:** linting, type checking, async-native testing

**Critical version constraints:**
- Pin Python to `3.12` in Dockerfiles (not `3.13`, not `latest`)
- Use `python:3.12-slim` base image (not Alpine — C extension compilation fails on musl libc)
- Pin MySQL to `mysql:8.4` for reproducibility

### Expected Features

The feature set maps cleanly onto phased delivery. Every table-stakes feature (Note CRUD, tags, collections, FTS, auth, pagination, Swagger) must ship before AI features are meaningful. The AI features exist on two levels: local (Ollama summarization and tagging — private, fast, no cost) and cloud (RAG Q&A — the headline feature that justifies the project).

**Must have (v1 table stakes):**
- Note CRUD (title, content, source_url, timestamps) — everything else depends on this
- User auth + JWT + per-user data isolation — multi-user is a stated requirement and learning goal
- Tags (many-to-many) + Collections (flat, no nesting in v1) — minimum expected organization
- MySQL full-text search (FULLTEXT index, MATCH AGAINST in boolean mode) — core retrieval value
- OpenAPI/Swagger auto-docs, proper HTTP status codes, pagination, filtering — Swagger IS the v1 UI

**Should have (competitive differentiators):**
- Auto-summarization via Ollama (`POST /ai/summarize`) — local LLM, private, demonstrates routing
- Auto-tagging via Ollama (`POST /ai/suggest-tags`) — low incremental cost once summarize works
- RAG Q&A (`POST /ai/ask`) — the "wow" feature; requires embedding infrastructure
- Related notes via vector similarity (`GET /notes/{id}/related`) — trivial once RAG infra exists

**Defer to v1.x (add after core pipeline validates):**
- Async job status endpoint (jobs table, poll-based)
- Semantic search as standalone endpoint
- Rate limiting on AI endpoints (slowapi)
- Bulk markdown export

**Defer to v2+:**
- Minimal HTML UI (Jinja2, not SPA)
- Note version history
- File attachments
- Public share links

### Architecture Approach

The architecture is a standard layered FastAPI application organized by domain (not by file type). Each domain (`notes/`, `auth/`, `tags/`, `collections/`, `ai/`, `search/`) contains its own router, schemas, models, service, and repository. The `ai/` domain is a first-class citizen with its own LLM router, Ollama client, cloud client, embed service, and RAG service. Configuration flows exclusively via `pydantic-settings` + environment variables (12-factor). There are three Docker Compose files: base, dev override (auto-applied), and prod override (explicit). The embedding pipeline (chunk -> embed -> store) runs as a FastAPI `BackgroundTask` so note creation is not blocked by inference.

**Major components:**
1. **FastAPI API container** — routers (HTTP), services (business logic), repositories (SQL), AI services (LLM routing + RAG). Port 8000 exposed to host; all others on internal Docker network only.
2. **MySQL 8.4 container** — relational store for users, notes, tags, collections, note_chunks. FULLTEXT index on `notes(title, content)`. `embedding JSON` column in `note_chunks` for v1 RAG.
3. **Ollama container** — local inference: `llama3.2:3b` (summarize/tag), `nomic-embed-text` (embeddings). Memory-limited in Compose; `OLLAMA_NUM_PARALLEL=1` to prevent OOM.
4. **Cloud LLM API (Anthropic)** — external HTTPS; used only for RAG answer generation. API key injected at runtime via env var, never in the image.
5. **GitHub Actions CI/CD** — lint (ruff) -> type-check (mypy) -> test (pytest + MySQL service container) -> build image -> push to GHCR on tag.

### Critical Pitfalls

The research identified 22 pitfalls. The five highest-impact ones for this project:

1. **Sync SQLAlchemy in async FastAPI routes** — use `create_async_engine` + `AsyncSession` + `asyncmy` from Phase 1, day one. Retrofitting is expensive. Warning sign: `from sqlalchemy.orm import Session` anywhere in deps.
2. **Missing `WHERE user_id = ?` in data queries** — authentication (JWT valid?) and authorization (owns this resource?) are separate. Every repository method for user-owned data must include the user_id filter. Write a cross-user access test per resource type in Phase 2.
3. **MySQL charset not utf8mb4 from day one** — set in three places simultaneously: Docker Compose command, SQLAlchemy connection string, Alembic defaults. Migrating charset after data exists is a painful table rebuild.
4. **RAG pitfall cluster (Phase 5)** — five independent problems that must all be addressed: stale embeddings after note edits, no relevance threshold (hallucinated "grounded" answers), bad chunking (fixed-character splits), prompt injection via stored notes, cloud LLM cost blowup from unbounded context.
5. **Secrets in git history** — add `.env` to `.gitignore` and `.gitattributes` (LF line endings) before the first commit. CRLF in shell scripts breaks Linux containers (Windows-specific trap that cannot be fixed without destructive git history rewriting).

---

## Implications for Roadmap

### Phase 0: Repo Foundation
**Rationale:** Infrastructure that cannot be safely added after the first commit. Secrets in git history require destructive `git filter-repo`; CRLF in scripts silently breaks containers on Windows.
**Delivers:** Initialized Python project (uv), `.gitignore` with `.env`, `.gitattributes` with `eol=lf`, empty FastAPI app skeleton, `docker-compose.yml` base, `pyproject.toml` with ruff/mypy/pytest config, GitHub repo, initial CI lint job.
**Avoids:** Pitfalls 14 (secrets in git), 15 (CRLF line endings), 22 (image versioning setup)
**Research flag:** Standard patterns — skip research phase.

### Phase 1: Database + API Skeleton
**Rationale:** Everything else requires notes to exist. This phase establishes the async database pattern that all subsequent phases inherit — getting it wrong here means refactoring every subsequent feature.
**Delivers:** MySQL 8.4 container with utf8mb4, Alembic baseline migration, async SQLAlchemy engine with `asyncmy`, Note CRUD endpoints (all notes public, no auth yet), MySQL FULLTEXT search (with `innodb_ft_min_token_size=2`), OpenAPI docs, pagination + filtering, all working via Swagger in Docker.
**Addresses:** Note CRUD, full-text search, OpenAPI docs (table stakes features)
**Uses:** FastAPI 0.115.x, SQLAlchemy 2.x, asyncmy, Alembic, pydantic-settings
**Avoids:** Pitfalls 1 (sync SQLAlchemy), 2 (session leak), 3 (utf8mb4), 4 (create_all vs Alembic), 5 (N+1 on tags), 6 (FULLTEXT min token size)
**Research flag:** Standard patterns — skip research phase. FastAPI + SQLAlchemy async is extensively documented; STACK.md has exact code patterns.

### Phase 2: Auth + Per-User Data Isolation
**Rationale:** Auth must exist before any user-facing feature is meaningful. JWT token handling and per-user query isolation are simpler to build once, before any other feature has been coded against an unprotected API.
**Delivers:** User registration + login, JWT access tokens (15-min expiry) + rotating refresh tokens stored in DB, `get_current_user` dependency wired into all note endpoints, per-user row isolation at service layer, cross-user access integration tests passing in CI.
**Addresses:** User auth + JWT + per-user data isolation (table stakes)
**Uses:** PyJWT 2.x, pwdlib[argon2], `refresh_tokens` table (add to schema here — not in ARCHITECTURE.md skeleton)
**Avoids:** Pitfalls 12 (JWT without expiry/refresh), 13 (missing user isolation)
**Research flag:** Standard patterns — skip research phase.

### Phase 3: Tags, Collections, REST Surface Polish
**Rationale:** Completes the table-stakes feature set. Tags (many-to-many) teach the relational joins that are an explicit learning goal. Collections add the coarse organizational layer users expect.
**Delivers:** Tag CRUD + many-to-many `note_tags`, Collection CRUD + `note_collections`, filtering/sorting on note list, consistent `ErrorResponse` schema, `selectinload` on all tag/collection relationships.
**Addresses:** Tags, collections, filtering/sorting (table stakes)
**Avoids:** Pitfall 5 (N+1 queries on tag relationships — use `selectinload`)
**Research flag:** Standard patterns — skip research phase.

### Phase 4: Local AI (Ollama)
**Rationale:** Ollama is the simpler LLM integration (no billing, no rate limits). Building the LLM provider abstraction here establishes the pattern the cloud client will plug into in Phase 5.
**Delivers:** Ollama service in Docker Compose (memory-limited, `OLLAMA_NUM_PARALLEL=1`), `POST /ai/summarize` and `POST /ai/suggest-tags` endpoints, LLM provider abstraction (BaseLLMClient ABC + OllamaClient), mock LLM client for tests, `llama3.2:3b` and `nomic-embed-text` models pre-pulled.
**Addresses:** Auto-summarization, auto-tagging (differentiator features)
**Uses:** ollama Python AsyncClient, FastAPI BackgroundTasks, tenacity for retry
**Avoids:** Pitfalls 17 (Ollama OOM), 19 (non-deterministic LLM tests — mock client required)
**Research flag:** May benefit from brief research on Ollama model sizing and Docker resource tuning on Windows Docker Desktop.

### Phase 5: RAG Pipeline (Embeddings + Cloud LLM)
**Rationale:** The headline feature. Requires the embedding infrastructure, which requires Ollama (Phase 4). This is the most complex phase — five independent pitfalls must all be addressed before the first line of code.
**Delivers:** `note_chunks` table (Alembic migration), EmbedService (chunk with overlap -> embed via `nomic-embed-text` -> store as JSON in MySQL), BackgroundTask hook on note create/update/delete, cosine similarity search with relevance threshold, `POST /ai/ask` RAG endpoint, `GET /notes/{id}/related`, cloud LLM mock for CI tests, `EMBEDDING_PROVIDER` env var switch.
**Addresses:** RAG Q&A, related notes (differentiator features — the core project value)
**Uses:** anthropic SDK (AsyncAnthropic), `claude-sonnet-4-5` as default model
**Avoids:** Pitfalls 7 (embedding design — JSON columns with upgrade path documented), 8 (prompt injection), 9 (no relevance threshold), 10 (bad chunking), 11 (stale embeddings), 18 (cloud LLM cost blowup)
**Research flag:** REQUIRES research phase. RAG pipeline has many moving parts. Key decision to confirm at start of Phase 5 planning: MySQL 8.4 JSON columns (current plan) vs MySQL 9.0+ native VECTOR type vs Qdrant sidecar — make this explicitly before writing any embed code.

### Phase 6: CI/CD Hardening + Portfolio Readiness
**Rationale:** CI/CD is a stated first-rank learning objective. A green CI pipeline with versioned Docker images makes this a portfolio-quality repo.
**Delivers:** GitHub Actions `ci.yml` (lint -> typecheck -> test with MySQL healthcheck, never `sleep`), `release.yml` (semver tag -> build + push to GHCR with SHA + version tags), `docker-compose.prod.yml` (gunicorn workers, no bind mounts), non-root `USER` in Dockerfile, `.dockerignore` excluding `.env`, secrets audit, `README.md`.
**Addresses:** DevOps, CI/CD, versioning (stated learning objectives)
**Uses:** GitHub Actions, GHCR, gunicorn + UvicornWorker, structlog JSON logs
**Avoids:** Pitfalls 16 (running as root), 20 (secrets in CI logs), 21 (flaky CI DB race condition), 22 (images without version tags)
**Research flag:** Standard patterns — skip research phase.

### Phase Ordering Rationale

- **Phase 0 before everything:** The two non-retrofittable pitfalls (secrets in git, CRLF) must be addressed before the first real commit.
- **Phase 1 before Phase 2:** Auth requires a User model; the User model belongs in the database layer. Testing auth requires notes to exist.
- **Phase 2 before Phase 3:** Tags and collections are user-owned resources requiring `user_id` isolation, which requires auth to exist.
- **Phase 3 before Phase 4:** Ollama summarization is only meaningful if notes exist for a real user.
- **Phase 4 before Phase 5:** Phase 5 uses Ollama for embeddings. The Ollama service, Docker Compose config, and OllamaClient abstraction must exist first.
- **Phase 6 after Phase 5:** The full Docker image (all features) is what gets published. CI lint/test jobs can begin after Phase 1, but the release pipeline waits for the complete app.

### Research Flags

**Requires research phase before planning:**
- **Phase 5 (RAG Pipeline):** Highest-complexity phase. Needs research on chunking strategy, cosine similarity threshold tuning for `nomic-embed-text` 768-dim space, prompt boundary patterns, token budget enforcement with Anthropic SDK, and the MySQL 8.4 JSON vs MySQL 9.0 VECTOR vs Qdrant decision.

**May benefit from brief research:**
- **Phase 4 (Ollama):** Model sizing for Windows Docker Desktop, `BackgroundTasks` vs async task queue tradeoffs.

**Standard patterns — skip research phase:**
- Phase 0, Phase 1, Phase 2, Phase 3, Phase 6 — all use well-documented patterns with exact code examples in STACK.md and ARCHITECTURE.md.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries verified against official docs via Context7. Version pins verified. Deprecated libraries identified with replacements. |
| Features | HIGH | Cross-validated across Obsidian, Notion, Logseq, Trilium, Mem, Readwise, and FastAPI ecosystem docs. Feature dependency graph is reliable. |
| Architecture | HIGH | Multiple authoritative sources cross-verified. Domain-per-folder pattern endorsed by FastAPI best-practices community repo. |
| Pitfalls | HIGH | All 22 pitfalls verified against official docs, GitHub issues, and post-mortems. Phase-to-pitfall mapping is specific and actionable. |

**Overall confidence:** HIGH

### Gaps to Address

- **Vector storage final decision:** MySQL 8.4 JSON (current recommendation) is correct for Phase 5 start, but the decision to stay there vs migrate to MySQL 9.0+ VECTOR type vs add Qdrant must be made explicitly at Phase 5 planning time. Check available MySQL image versions and measure cosine similarity loop latency at 1k chunks before deciding.
- **Refresh token storage:** PITFALLS.md recommends server-side refresh token storage (DB table). The schema skeleton in ARCHITECTURE.md does not include a `refresh_tokens` table. This must be added to the Phase 2 schema before the auth migration is created.
- **Ollama CPU performance on Windows Docker Desktop:** STACK.md notes 5-30s per summarization request on CPU with a 3B model. Test actual latency on the specific hardware before Phase 4 planning.
- **Anthropic model IDs:** STACK.md lists `claude-sonnet-4-5` and `claude-haiku-4-5` as verified current model IDs (2026-06-23). Re-verify at Phase 5 planning time as model naming conventions evolve.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/fastapi/fastapi` — lifespan, OAuth2, dependency injection patterns
- Context7 `/websites/sqlalchemy_en_20` — asyncmy/aiomysql engine creation, async dialect
- Context7 `/websites/alembic_sqlalchemy` — async env.py migration pattern
- Context7 `/anthropics/anthropic-sdk-python` — model IDs, AsyncAnthropic usage
- Context7 `/ollama/ollama-python` — AsyncClient, chat, embed
- Context7 `/qdrant/qdrant-client` — AsyncQdrantClient, upsert, query_points
- Context7 `/jpadilla/pyjwt` — encode/decode HS256
- MySQL 8.4 Reference Manual — utf8mb4, FULLTEXT fine-tuning, InnoDB indexes
- SQLAlchemy 2.0 asyncio documentation — async session, engine, driver compatibility
- OWASP LLM01:2025 — Prompt Injection

### Secondary (MEDIUM confidence)
- zhanymkanov/fastapi-best-practices — project structure, DI patterns, N+1 prevention
- FastAPI GitHub Discussion #10450 — QueuePool exhaustion patterns
- FastAPI PR #13917 — official migration from passlib to pwdlib
- Snorkel AI — RAG failure modes (relevance threshold, chunking, staleness)
- WebSearch: Ollama model recommendations 2025-2026
- WebSearch: uv package manager 2026 recommendations
- Obsidian, Notion, Logseq, Trilium feature surveys (2026)

### Tertiary (LOW confidence)
- WebSearch: MySQL 9.0 VECTOR type production readiness — needs validation at Phase 5 planning time before committing to that upgrade path

---

*Research completed: 2026-06-23*
*Ready for roadmap: yes*
