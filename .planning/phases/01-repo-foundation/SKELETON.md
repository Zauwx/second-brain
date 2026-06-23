# Walking Skeleton — Second Brain

**Phase:** 1
**Generated:** 2026-06-23

## Capability Proven End-to-End

> One sentence: the smallest user-visible capability that exercises the full stack.

A developer can run `docker compose up`, open Swagger at `http://localhost:8000/docs`, and call `GET /health` which returns `200 {"status": "ok"}` — proving the full toolchain (uv install → FastAPI app → uvicorn → Docker container → host browser) works end to end before any feature is built.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Language / runtime | Python 3.12 | Locked in CLAUDE.md + STATE.md; 3.13 drops `crypt` (breaks future passlib alternatives), full asyncio support. Pinned in Dockerfile. |
| API framework | FastAPI 0.115.x | Auto OpenAPI/Swagger, async-native, Pydantic v2, project learning goal (REST/HTTP). |
| ASGI server (dev) | Uvicorn 0.32.x with `--reload` | Reference ASGI server; hot reload in dev via compose override pattern (override deferred to later phase). |
| Config / settings | pydantic-settings 2.x `BaseSettings` in `app/core/config.py` | 12-factor config from env vars; retrofitting later is painful (D-11). |
| Package manager | uv | 10-100x faster than pip; single tool for deps/venv/lockfile; used in Dockerfile too (D-08). |
| Lint / format | ruff (>=0.8.0) configured in `pyproject.toml` | Replaces black+isort+flake8; success criterion 4 gates on `uv run ruff check app/`. |
| Type checker | mypy (>=1.13.0) targeting py3.12 | Catches async signature errors early; configured in `pyproject.toml`. |
| Base image | `python:3.12-slim` (Debian) | NOT Alpine — musl breaks asyncmy/Cython/cryptography compilation later (D-12, CLAUDE.md "What NOT to Use"). |
| Project layout | Domain-per-folder under `app/` (`app/core`, `app/api`, plus empty domain placeholders) | Seeds the Router→Service→Repository convention so Phase 2 slots in cleanly (D-07, ARCHITECTURE.md). |
| Source control | Public GitHub repo `second-brain` via `gh` CLI, MIT license | Explicit portfolio goal; public history from commit one (D-01/D-02/D-03/D-05). |

## Stack Touched in Phase 1

- [x] Project scaffold (uv-managed `pyproject.toml`, ruff, mypy, FastAPI)
- [x] Routing — at least one real route (`GET /health` via `app/api/health.py` router)
- [ ] Database — N/A this phase (MySQL deferred to Phase 2; `.env.example` carries the placeholders only)
- [x] UI — Swagger UI at `/docs` is the interactive surface; `GET /health` exercised through it
- [x] Deployment — `docker compose up` runs the api service; documented quickstart in README actually works

## Out of Scope (Deferred to Later Slices)

> Anything that is *not* in the skeleton. Explicit so future phases do not re-litigate Phase 1's minimalism.

- MySQL service in Compose, async SQLAlchemy engine, Alembic migrations — Phase 2.
- Note CRUD, schemas, repositories, services with real logic — Phase 2 (domain folders are empty placeholders only).
- JWT auth, users, per-user isolation — Phase 3.
- Tags, collections, FULLTEXT search — Phase 4.
- Ollama service + local LLM features — Phase 5.
- RAG pipeline (embeddings, cloud LLM) — Phase 6.
- `docker-compose.override.yml` (dev bind-mounts/reload split), `docker-compose.prod.yml`, gunicorn prod command — Phase 7.
- CI workflow (`ci.yml`), versioned image build/push, non-root `USER` hardening — Phase 7 (README carries a CI badge placeholder only).

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: User can create/read/update/delete notes via Swagger, backed by async MySQL + Alembic.
- Phase 3: Every note endpoint requires a JWT; each user sees only their own data.
- Phase 4: Users organize notes with tags and collections and keyword-search them.
- Phase 5: Users trigger local-LLM summarization and tag suggestion via Ollama.
- Phase 6: Users ask natural-language questions answered from their own notes (RAG).
- Phase 7: Green CI pipeline, versioned images, prod Compose, secrets audit — portfolio-ready.
