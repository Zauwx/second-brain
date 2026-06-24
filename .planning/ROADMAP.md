# Roadmap: Second Brain — Personal Knowledge Base with AI

## Overview

Seven phases, each building on the last. Phase 1 locks in the repo hygiene that cannot be retrofitted. Phases 2-4 build the full relational API surface (notes, auth, tags, collections, full-text search) — the foundation that makes AI features meaningful. Phases 5-6 add the two LLM tiers (local Ollama, cloud RAG). Phase 7 hardens CI/CD and makes the repo portfolio-ready. Every phase delivers a runnable, testable vertical slice. Every requirement maps to exactly one phase.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Repo Foundation** - Git hygiene, project scaffold, and Docker base that cannot be safely added after the first commit
- [ ] **Phase 2: Database + API Skeleton** - Async MySQL, Alembic migrations, Note CRUD, OpenAPI docs, pagination, and tests — all working in Docker
- [ ] **Phase 3: Auth + Per-User Data Isolation** - JWT auth with refresh tokens, per-user query isolation, and cross-user access tests in CI
- [ ] **Phase 4: Tags, Collections, Full-Text Search** - Many-to-many tags, collections, MySQL FULLTEXT search, and REST surface polish
- [ ] **Phase 5: Local AI (Ollama)** - Ollama service in Docker, LLM provider abstraction, auto-summarization, and auto-tagging via local LLM
- [ ] **Phase 6: RAG Pipeline** - Embedding pipeline, note_chunks store, cosine similarity search, natural-language Q&A, and related-notes via cloud LLM
- [ ] **Phase 7: CI/CD Hardening + Portfolio Readiness** - GitHub Actions lint/test/build/release pipeline, prod Compose, versioned images, secrets audit

## Phase Details

### Phase 1: Repo Foundation
**Goal**: The repository exists with all non-retrofittable hygiene in place — secrets excluded from git history forever, line endings fixed for Linux containers, and a minimal runnable FastAPI skeleton confirmed in Docker
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: OPS-05
**Success Criteria** (what must be TRUE):
  1. `git log --all -- .env` returns nothing; `.env` is in `.gitignore` and `.env.example` is committed with placeholder values
  2. `.gitattributes` forces LF for all text files; a shell script created on Windows starts without `^M: bad interpreter` errors inside a Linux container
  3. `docker compose up` starts the FastAPI skeleton and `GET /health` returns 200 via Swagger UI at `http://localhost:8000/docs`
  4. `uv run ruff check app/` passes with zero errors on the skeleton code
**Plans**: 3 plans
- [x] 01-01-PLAN.md — Repo hygiene + portfolio docs (.gitignore, .gitattributes, .env.example, LICENSE, README)
- [x] 01-02-PLAN.md — uv-managed FastAPI skeleton: ruff/mypy config, pydantic-settings, GET /health, domain layout
- [ ] 01-03-PLAN.md — Dockerize (python:3.12-slim) + compose, end-to-end /health via Swagger, create + push public repo

### Phase 2: Database + API Skeleton
**Goal**: A fully working Note CRUD API backed by async MySQL runs in Docker — Alembic manages the schema, async SQLAlchemy + asyncmy handle all queries, Swagger is the UI, pagination and tests are included
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: NOTE-01, NOTE-02, NOTE-03, NOTE-04, API-01, API-02, API-03, OPS-01
**Success Criteria** (what must be TRUE):
  1. User can create, read, update, and delete notes (with text content and optional source URL) via Swagger UI running in Docker — no auth required at this phase
  2. `GET /notes` returns paginated results with `?page=`, `?sort=`, and `?filter=` query parameters and correct HTTP status codes (200, 201, 404, 422)
  3. `GET /docs` serves live OpenAPI/Swagger documentation auto-generated from the FastAPI app
  4. `alembic upgrade head` runs in the container and creates all tables with `utf8mb4` charset — `Base.metadata.create_all()` is absent from startup
  5. `pytest tests/ --asyncio-mode=auto` passes with coverage of core note endpoints using a real MySQL service container (no mocks for DB)
  6. `docker compose up` starts api + mysql; only the api port (8000) is exposed to the host
**Plans**: TBD

### Phase 3: Auth + Per-User Data Isolation
**Goal**: Every note endpoint requires a valid JWT; each user sees only their own data; refresh token rotation is in place; cross-user access tests pass in CI
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. User can register with email and password (`POST /auth/register`) and receive a 201 response
  2. User can log in (`POST /auth/login`) and receive a short-lived access token (15-min expiry) plus a rotating refresh token stored in the `refresh_tokens` DB table
  3. User can call `POST /auth/refresh` with a valid refresh token to receive a new access token without re-entering credentials — old refresh token is invalidated on rotation
  4. Calling `GET /notes` or `GET /notes/{id}` with a valid JWT for user A never returns notes belonging to user B — verified by an integration test that asserts 403/404 on cross-user access
  5. Calling any protected endpoint with no token or an expired token returns 401
**Plans**: TBD

### Phase 4: Tags, Collections, Full-Text Search
**Goal**: Users can organize notes with tags (many-to-many) and collections, and search notes by keyword using MySQL FULLTEXT — completing the full table-stakes REST surface
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: ORG-01, ORG-02, ORG-03, ORG-04, SRCH-01
**Success Criteria** (what must be TRUE):
  1. User can create tags and attach or detach them from notes; `GET /notes` with `?tag=python` returns only notes tagged with that tag (many-to-many join works with `selectinload`, no N+1 queries)
  2. User can filter notes by multiple tags simultaneously (e.g., `?tag=python&tag=docker`)
  3. User can create a collection, add notes to it, and `GET /collections/{id}/notes` returns the notes in that collection
  4. `GET /search?q=docker` returns notes whose title or content contains "docker" using `MATCH ... AGAINST ... IN BOOLEAN MODE`; searching for 2-character terms like "AI" also returns results (`innodb_ft_min_token_size=2` confirmed via `SHOW VARIABLES`)
  5. All tag and collection resources are isolated per user — user A cannot read or modify user B's tags or collections
**Plans**: TBD

### Phase 5: Local AI (Ollama)
**Goal**: Ollama runs as a Docker service alongside the API; users can trigger automatic summarization and tag suggestion for any note via a local LLM — no cloud calls, no billing, provably private
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: AIL-01, AIL-02
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts the api, mysql, and ollama services; `GET /health` confirms ollama is reachable from the api container on the internal Docker network
  2. `POST /ai/summarize` with a note ID returns a 2-3 sentence summary generated by `llama3.2:3b` via Ollama within the Docker network — the HTTP response is not blocked by inference (BackgroundTask or direct call completes before timeout)
  3. `POST /ai/suggest-tags` with a note ID returns a JSON list of suggested tag strings generated by the local LLM
  4. `docker stats` shows the Ollama container staying within its configured memory limit during a summarization request (OOM guard confirmed)
  5. All pytest LLM tests pass using a mock LLM client — zero calls to the real Ollama service in the test suite
**Plans**: TBD

### Phase 6: RAG Pipeline
**Goal**: Users can ask a natural-language question and receive an answer grounded in their own notes with source citations; users can also retrieve notes similar to a given note — the headline feature of the project
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: RAG-01, RAG-02
**Success Criteria** (what must be TRUE):
  1. `POST /ai/ask` with a natural-language question returns an answer citing source note IDs, where the answer is demonstrably drawn from the user's stored notes (RAG pipeline: embed question → cosine similarity search over `note_chunks` → prompt cloud LLM with top-k chunks above relevance threshold)
  2. When no notes are relevant (similarity scores all below threshold), `POST /ai/ask` returns a "no relevant notes found" response rather than a hallucinated answer
  3. `GET /notes/{id}/related` returns a list of notes that are semantically similar to the given note, based on stored embeddings
  4. Editing or deleting a note triggers re-embedding or chunk removal in `note_chunks` — stale embeddings do not persist after note update (verified by searching for old content after edit)
  5. All RAG pytest tests use a mock cloud LLM client and a mock embed service — zero calls to Anthropic API in the test suite
**Plans**: TBD
**UI hint**: no

### Phase 7: CI/CD Hardening + Portfolio Readiness
**Goal**: A green GitHub Actions pipeline runs on every push; a versioned Docker image is built and pushed to GHCR on every semver tag; the prod Compose configuration is ready; the repo is portfolio-presentable
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: OPS-02, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):
  1. `git push` to any branch triggers the `ci.yml` workflow: ruff lint → mypy typecheck → pytest with MySQL healthcheck (no `sleep`) → all steps green in GitHub Actions
  2. Pushing a `v*.*.*` semver tag triggers `release.yml`: builds a Docker image tagged with both the semver version and the git SHA, pushes both tags to GHCR, and creates a GitHub Release with auto-generated notes
  3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` starts the app using a gunicorn + UvicornWorker command with a pre-built versioned image (no bind mounts, no `--reload`)
  4. `docker exec <api-container> whoami` returns a non-root user; `docker history <image>` contains no secret values; no `.env` file exists inside the image filesystem
  5. `docker compose -f docker-compose.yml -f docker-compose.prod.yml` uses a separate `.env.prod` file (gitignored); dev and prod configs are clearly separated with no commented-out blocks
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Repo Foundation | 2/3 | In Progress|  |
| 2. Database + API Skeleton | 0/TBD | Not started | - |
| 3. Auth + Per-User Data Isolation | 0/TBD | Not started | - |
| 4. Tags, Collections, Full-Text Search | 0/TBD | Not started | - |
| 5. Local AI (Ollama) | 0/TBD | Not started | - |
| 6. RAG Pipeline | 0/TBD | Not started | - |
| 7. CI/CD Hardening + Portfolio Readiness | 0/TBD | Not started | - |
