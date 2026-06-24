# Second Brain

A self-hosted personal knowledge base with natural-language Q&A — save notes, organize with tags and collections, and query your own knowledge using local and cloud AI.

<!-- CI badge — wired in Phase 7 (GitHub Actions pipeline) -->
<!-- ![CI](https://github.com/YOUR_USERNAME/second-brain/actions/workflows/ci.yml/badge.svg) -->

---

## What It Does

- Save notes, articles, and links with full-text search (MySQL FULLTEXT)
- Organize with tags (many-to-many) and collections
- Ask questions in natural language and get answers grounded in your own notes (RAG via Anthropic Claude)
- Auto-generate summaries and suggested tags via a local LLM (Ollama)
- Multi-user with JWT auth and full data isolation per user

> **Phase 1 (current):** Foundation only — repository hygiene, FastAPI skeleton, and `GET /health`. Application features ship in later phases.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| API framework | FastAPI 0.115 + Uvicorn |
| Database | MySQL 8.4 (InnoDB, utf8mb4, FULLTEXT) |
| ORM / migrations | SQLAlchemy 2.x async + Alembic |
| Auth | JWT (PyJWT) + Argon2 password hashing (pwdlib) |
| Local AI | Ollama (llama3.2:3b for summarization, nomic-embed-text for embeddings) |
| Cloud AI | Anthropic Claude (RAG Q&A) |
| Infrastructure | Docker + Docker Compose (dev/live + prod) |
| Package manager | uv |
| Linting / typing | ruff + mypy |
| CI/CD | GitHub Actions |

---

## Quickstart (Phase 1 — Foundation)

Prerequisites: Docker Desktop running on Windows (or Docker + Docker Compose on Linux/macOS).

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/second-brain.git
cd second-brain
cp .env.example .env
```

Edit `.env` and fill in real values. For Phase 1 (API skeleton only), only `ENVIRONMENT` and `LOG_LEVEL` matter — database and AI credentials are needed from Phase 2 onward.

### 2. Start services

```bash
docker compose up
```

Docker Compose starts the FastAPI API service. MySQL and Ollama are added in later phases.

### 3. Verify the API is running

Open your browser at:

```
http://localhost:8000/docs
```

The Swagger UI loads automatically. Click on `GET /health`, then "Try it out" and "Execute".

Expected response:

```json
{"status": "ok"}
```

A `200 OK` from `/health` confirms the API container is up and running correctly.

---

## Architecture

The application follows a **domain-per-folder** layout inside `app/`:

```
app/
  main.py          # FastAPI app factory, lifespan hooks, router registration
  core/            # Settings (pydantic-settings), JWT helpers, shared dependencies
  api/             # HTTP routers — one file per domain (health, notes, auth, ai, search)
  notes/           # Note CRUD — router, service, repository, schemas, ORM model
  tags/            # Tag many-to-many — same layered structure
  collections/     # Collection grouping — same layered structure
  auth/            # JWT registration/login, user model and isolation
  ai/              # Ollama (local LLM) and Anthropic (cloud RAG) clients + services
  search/          # Full-text and semantic search
```

Three services run as Docker containers connected on an internal network:

- **api** — FastAPI application (Uvicorn in dev, Gunicorn in prod), exposed on port 8000
- **mysql** — MySQL 8.4, internal network only (not exposed to host in prod)
- **ollama** — Local LLM runtime, internal network only

Cloud LLM calls (Anthropic) go out over HTTPS directly from the API container. The API key is injected at runtime via `.env` — it never enters the Docker image.

---

## Project Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 — Repo Foundation | `.gitignore`, `.gitattributes`, `.env.example`, LICENSE, README, FastAPI skeleton, `GET /health` | In progress |
| 2 — Database + Notes CRUD | MySQL, SQLAlchemy async, Alembic, Notes/Tags/Collections API | Planned |
| 3 — Auth + Data Isolation | JWT multi-user, per-user data scoping | Planned |
| 4 — Local AI (Ollama) | Summarization, auto-tagging via local LLM | Planned |
| 5 — RAG + Cloud AI | Embeddings, vector similarity, Claude-powered Q&A | Planned |
| 6 — Search | MySQL FULLTEXT + semantic search merge | Planned |
| 7 — CI/CD + Production | GitHub Actions pipeline, Docker image tagging, prod Compose | Planned |

---

## Development

```bash
# Install dependencies (requires uv)
uv sync

# Run linter
uv run ruff check app/

# Run type checker
uv run mypy app/

# Run tests
uv run pytest

# Start with hot-reload (dev)
docker compose up
```

---

## License

MIT — see [LICENSE](LICENSE).
