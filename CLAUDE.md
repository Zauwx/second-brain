<!-- GSD:project-start source:PROJECT.md -->
## Project

**Second Brain — Base de connaissances personnelle avec IA**

Une application "second brain" auto-hébergée : l'utilisateur sauvegarde des notes, articles et liens, les organise (tags, collections) et interroge sa propre base de connaissances en langage naturel. C'est avant tout un **projet d'apprentissage fil-rouge** : il sert de support concret pour monter en compétences sur MySQL, les REST API / HTTP, l'IA générative (LLMs locaux et cloud), Docker, Linux, et un vrai pipeline CI/CD + versioning. Pour : le développeur lui-même, comme outil personnel **et** comme pièce maîtresse de son profil GitHub.

**Core Value:** L'utilisateur peut sauvegarder du contenu et **retrouver / interroger ses connaissances en langage naturel** (RAG) — c'est la fonction qui doit marcher avant tout le reste.

### Constraints

- **Tech stack**: Python + FastAPI (backend/API) — meilleur écosystème IA/LLM, doc Swagger auto, très demandé.
- **Tech stack**: MySQL (base de données) — objectif d'apprentissage explicite ; modèle relationnel riche attendu (jointures, many-to-many, index, full-text).
- **Tech stack**: Docker / Docker Compose — environnements dev/live + prod ; tout conteneurisé.
- **Tech stack**: IA hybride — Ollama (local) + une API LLM cloud (Claude/OpenAI) pour le RAG.
- **Plateforme**: Développement sur Windows via Docker Desktop ; conteneurs Linux (apprentissage Linux ciblé).
- **DevOps**: GitHub + CI/CD (GitHub Actions) + versioning sémantique — exigence de premier rang, pas un accessoire.
- **Sécurité**: Auth JWT multi-utilisateur avec isolation des données ; secrets hors du repo.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | LTS release, full asyncio support, required by all libs below. 3.13 drops `crypt` module (breaking passlib) so pin to 3.12 in Dockerfiles. |
| FastAPI | 0.115.x | API framework | The de facto standard for Python async REST APIs: auto-generates OpenAPI/Swagger, first-class Pydantic v2 support, async-native, massive ecosystem. |
| Pydantic | 2.x (bundled with FastAPI) | Data validation & serialization | v2 is 5-50× faster than v1 (rewritten in Rust). Use `model_config = ConfigDict(from_attributes=True)` for ORM mode. Do NOT use v1. |
| Uvicorn | 0.32.x | ASGI server (dev) | The reference ASGI implementation. Use `uvicorn main:app --reload` in dev. |
| Gunicorn + uvicorn workers | latest | ASGI server (prod) | In prod, Gunicorn manages process lifecycle; Uvicorn `UvicornWorker` handles requests. Pattern: `gunicorn main:app -k uvicorn.workers.UvicornWorker`. |
| SQLAlchemy | 2.x | ORM + async DB layer | The standard Python ORM. v2 introduced the async extension (`sqlalchemy.ext.asyncio`) as stable. Use `DeclarativeBase` (not the legacy `declarative_base()`). |
| asyncmy | 0.2.x | Async MySQL driver | Preferred over `aiomysql` (which is unmaintained since 2021 per SQLAlchemy changelog). asyncmy is Cython-accelerated, actively maintained, API-compatible. Connection string: `mysql+asyncmy://user:pass@host/db?charset=utf8mb4`. |
| Alembic | 1.14.x | DB migrations | The standard SQLAlchemy migration tool. Requires async env.py adaptation (see patterns section). Non-negotiable for any real project. |
| Qdrant | 1.x (server) / qdrant-client 1.x (Python) | Vector store for RAG | Best-in-class self-hosted vector DB: dedicated Docker image, async Python client (`AsyncQdrantClient`), cosine similarity, payload filtering. Runs as a separate Docker service. |
| Ollama | latest | Local LLM runtime | Standard way to run local models in Docker. Exposes an OpenAI-compatible REST API; use the `ollama` Python client for generation and the `AsyncClient` for async usage. |
| anthropic | 0.50.x | Cloud LLM SDK | Official Anthropic Python SDK. Use `AsyncAnthropic` for async RAG endpoints. See model IDs section. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyJWT | 2.x | JWT encode/decode | The standard, lightweight JWT library. FastAPI's own security tutorial uses `import jwt` (PyJWT). Do not use `python-jose` (unmaintained). |
| pwdlib[argon2] | 0.2.x | Password hashing | Modern replacement for passlib. passlib is broken on Python 3.13+ and unmaintained. `pwdlib` + Argon2id is the current FastAPI-users default. |
| sentence-transformers | 3.x | Local text embeddings | Generate embeddings from notes for Qdrant. Use `all-MiniLM-L6-v2` (22M params, 384 dims, fast) or pull via Ollama's `nomic-embed-text` to avoid a separate Python model download. |
| httpx | 0.28.x | Async HTTP client | Used as the test transport for FastAPI (`AsyncClient(transport=ASGITransport(app=app))`). Also useful to call Ollama's REST API directly if needed. |
| python-dotenv | 1.x | `.env` file loading | Load secrets from `.env` in dev; in prod, pass env vars via Docker Compose. |
| tenacity | 9.x | Retry logic | For LLM API calls (Ollama timeouts, Anthropic rate limits). Simple decorator-based retries. |
| pydantic-settings | 2.x | Typed settings management | Reads env vars into a Pydantic `BaseSettings` model. Integrates with FastAPI's DI system for config injection. |
| structlog | 24.x | Structured logging | JSON-structured logs for Docker log drivers and future observability. Better than stdlib `logging` for containerized apps. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Package manager and venv | Replaces pip + virtualenv. 10-100× faster. Use `uv init`, `uv add`, `uv run` — generates `pyproject.toml` + `uv.lock`. Use in Dockerfiles too (`pip install uv && uv sync --frozen`). |
| ruff | Linter + formatter | Replaces black + isort + flake8. Written in Rust, runs in milliseconds. Single config in `pyproject.toml`. Minimum version: 0.8.0. |
| mypy | Static type checker | Run with `--strict` to catch async signature errors early. Target `python_version = "3.12"`. Version ≥ 1.13.0. |
| pytest | Test runner | Version ≥ 8.0. Use `pytest-asyncio` for async test functions. |
| pytest-asyncio | Async test support | Required for `async def test_*` functions. Set `asyncio_mode = "auto"` in `pyproject.toml` to avoid decorator boilerplate. |
| httpx (AsyncClient) | Integration test client | Use `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` for full async integration tests without a live server. |
| pre-commit | Git hooks | Run ruff + mypy on commit. Catches issues before CI. |
| GitHub Actions | CI/CD | Lint → typecheck → test → build Docker image. Standard pipeline for this stack. |
## Detailed Recommendations by Focus Area
### FastAPI: ASGI, Lifespan, and Dependency Injection
### MySQL + SQLAlchemy 2: Async Pattern
### Alembic: Async env.py
### JWT Auth: PyJWT + pwdlib
# Hash on registration
# Verify on login
# Issue JWT
# Validate JWT
### Local LLM: Ollama Models and Client
| Model | Size | Use case | Pull command |
|-------|------|----------|--------------|
| `llama3.2:3b` | ~2 GB | Summarization, instruction-following | `ollama pull llama3.2:3b` |
| `qwen2.5:3b` | ~2 GB | Fast tagging, structured JSON output | `ollama pull qwen2.5:3b` |
| `nomic-embed-text` | 274 MB | Text embeddings for RAG | `ollama pull nomic-embed-text` |
### Cloud LLM: Anthropic Claude API
| Model | Use case |
|-------|----------|
| `claude-sonnet-4-5` | Best balance of quality/cost for RAG Q&A — recommended default |
| `claude-haiku-4-5` | Cheapest, fastest — use for high-volume or fallback |
| `claude-opus-4-0` | Most capable — overkill for RAG, expensive |
### Provider Abstraction Pattern
### RAG: Vector Pipeline (Hand-Rolled + Qdrant)
# Index a note
# Retrieve for RAG (user-scoped)
### MySQL Full-Text Search
### Docker: Service Architecture
- Expose only `api` ports to the host (8000); `mysql`, `qdrant`, `ollama` stay on the internal Docker network
- Use `healthcheck` + `depends_on: condition: service_healthy` so the API waits for MySQL to be ready
- Use `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, etc. from a `.env` file (never in `docker-compose.yml`)
- In prod, add `restart: unless-stopped` to all services
- Pre-bake Ollama models into a custom image for prod (avoids cold-start model download)
## Installation
# Initialize project with uv
# Core runtime dependencies
# Dev dependencies
## Alternatives Considered
| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Async MySQL driver | asyncmy | aiomysql | aiomysql unmaintained since 2021; SQLAlchemy docs flag it as "not working with recent Python versions" |
| Password hashing | pwdlib[argon2] | passlib | passlib is unmaintained; broken on Python 3.13 (removes `crypt` module); FastAPI-Users migrated to pwdlib in v13 |
| JWT library | PyJWT | python-jose | python-jose is abandoned/unmaintained; FastAPI's own tutorial now uses PyJWT directly |
| Vector store | Qdrant | ChromaDB | Qdrant has a proper production Docker image, async Python client, payload filtering (critical for multi-user data isolation), and active development. ChromaDB is fine for local scripts but its production story is weaker. |
| Embeddings | nomic-embed-text via Ollama | sentence-transformers in API container | Keeping embeddings in Ollama avoids shipping PyTorch into the FastAPI container (bloats image by ~2 GB). One fewer Python dependency to manage. |
| RAG orchestration | Hand-rolled | LangChain / LlamaIndex | This is a learning project — frameworks hide exactly the mechanics (chunking, embedding, retrieval, prompting) the user needs to understand. Add a framework later once the concepts are solid. |
| Package manager | uv | pip + requirements.txt | uv is 10-100× faster, handles lockfiles, venvs, and Python version in one tool. The 2026 standard for Python projects. |
| ORM | SQLAlchemy 2.x | Tortoise-ORM, SQLModel | SQLAlchemy has the widest ecosystem, Alembic integration, and async support. SQLModel is built on top of SQLAlchemy/Pydantic but adds a thin abstraction that obscures some async patterns worth learning. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `passlib` | Unmaintained; broken on Python 3.13 (`crypt` module removed); no active PRs | `pwdlib[argon2]` |
| `python-jose` | Abandoned project; known security issues unfixed | `PyJWT` |
| `aiomysql` | SQLAlchemy itself calls it "unmaintained and not working with recent Python versions" | `asyncmy` |
| SQLAlchemy 1.x / legacy `declarative_base()` | v2 has a completely new async API; v1 patterns don't translate | SQLAlchemy 2.x with `DeclarativeBase` |
| Alpine Linux base image | C extension compilation (asyncmy/Cython, cryptography) fails on musl libc without adding build tools, defeating the size benefit | `python:3.12-slim` (Debian-based) |
| LangChain for a first RAG | 130K LoC framework — hides chunking, embedding, retrieval behind abstractions you need to understand first | Hand-rolled RAG with `qdrant-client` |
| Sync SQLAlchemy in an async FastAPI | Blocks the event loop; defeats the purpose of async | `create_async_engine` + `async_sessionmaker` |
| PostgreSQL | Explicitly out of scope — project goal is to learn MySQL | MySQL 8.4 |
| `.env` secrets in Docker image / code | Leaks credentials into image layers and version control | Docker Compose `env_file`, GitHub Actions secrets |
## Stack Patterns by Variant
- Use `docker-compose.override.yml` to mount source code as a volume and enable `--reload`
- Ollama on CPU is slow for inference but fine for dev; expect 5-30s per summarization request with a 3B model
- MySQL persists data via a named Docker volume; recreating the container does not wipe data
- Use `gunicorn -k uvicorn.workers.UvicornWorker` with `--workers $(nproc)`
- Pin all image versions (`mysql:8.4.0`, `qdrant/qdrant:v1.11.0`) for reproducibility
- Use GitHub Actions to build and tag the API image; pull the tag on the host to deploy
- Add `deploy: resources: reservations: devices: - driver: nvidia` to the Ollama service
- Switch to `llama3.2:8b` for much better summarization quality (still fits in 8 GB VRAM at Q4)
- Inference drops from ~30s to ~1-2s
- Use MySQL FULLTEXT for keyword-based search (fast, no extra service)
- Use Qdrant for semantic Q&A (RAG pipeline, "find notes about X" even if X isn't a keyword)
- Both can coexist; they solve different problems
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.115.x | Pydantic 2.x | Pydantic v1 compat mode available but deprecated — do not use it |
| SQLAlchemy 2.x | asyncmy 0.2.x | Use `mysql+asyncmy://` DSN; `mysql+aiomysql://` also works but not recommended |
| Alembic 1.14.x | SQLAlchemy 2.x | Requires async env.py adaptation (see above); standard `alembic init` generates sync env.py |
| PyJWT 2.x | Python 3.12 | Import as `import jwt` — the package installs as `jwt` module |
| pwdlib 0.2.x | Python 3.12 | Requires `argon2-cffi` (installed via `pwdlib[argon2]` extra) |
| anthropic 0.50.x | Python 3.12 | Use `AsyncAnthropic` for async FastAPI handlers |
| qdrant-client 1.x | Python 3.12 | Use `AsyncQdrantClient` for async FastAPI handlers |
| python:3.12-slim | asyncmy (Cython) | glibc present on slim; C extensions compile correctly |
## Anthropic Model Reference (verified 2026-06-23)
| Model ID | Tier | Recommended Use |
|----------|------|-----------------|
| `claude-sonnet-4-5` | Mid | Default for RAG Q&A — best quality/cost balance |
| `claude-haiku-4-5` | Fast/cheap | High-frequency operations, development, fallback |
| `claude-opus-4-0` | Flagship | Complex reasoning only; expensive |
## Sources
- Context7 `/fastapi/fastapi` — lifespan, OAuth2, dependency injection patterns (HIGH)
- Context7 `/websites/sqlalchemy_en_20` — asyncmy/aiomysql engine creation, async dialect docs (HIGH)
- Context7 `/websites/alembic_sqlalchemy` — async env.py migration pattern (HIGH)
- Context7 `/anthropics/anthropic-sdk-python` — model IDs, AsyncAnthropic usage (HIGH)
- Context7 `/ollama/ollama-python` — AsyncClient, chat, embed (HIGH)
- Context7 `/qdrant/qdrant-client` — AsyncQdrantClient, upsert, query_points (HIGH)
- Context7 `/jpadilla/pyjwt` — encode/decode HS256 (HIGH)
- FastAPI GitHub Discussion #11773 — passlib maintenance status, pwdlib migration (MEDIUM)
- FastAPI PR #13917 — official migration from passlib to pwdlib in tutorial (MEDIUM)
- SQLAlchemy changelog 1.4 — asyncmy vs aiomysql maintainability note (HIGH via Context7)
- WebSearch: Ollama model recommendations 2025-2026 (MEDIUM — cross-referenced with Ollama library page)
- WebSearch: uv package manager 2026 recommendations (MEDIUM — consistent across multiple sources)
- WebSearch: pytest-asyncio + httpx AsyncClient FastAPI testing patterns (MEDIUM)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
