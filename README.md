<p align="center">
  <img src="assets/logo.png" alt="Second Brain logo" width="180" />
</p>

<h1 align="center">Second Brain</h1>

<p align="center">
  A self-hosted personal knowledge base with natural-language Q&A — save notes, articles, and links, organize them with tags and collections, and (in later phases) query your own knowledge using local and cloud AI.
</p>

<!-- CI badge — wired in Phase 7 (GitHub Actions pipeline) -->
<!-- ![CI](https://github.com/Zauwx/second-brain/actions/workflows/ci.yml/badge.svg) -->

---

## What It Does

- Save notes, articles, and links — full CRUD with pagination and sorting
- Organize with **tags** (many-to-many) and filter notes by tag (AND-intersection)
- Group notes into **collections**
- Keyword **full-text search** over titles and content via MySQL FULLTEXT
- Multi-user with **JWT auth** (access + refresh tokens) and full **per-user data isolation**
- Auto-generate **summaries** from a local LLM (Ollama), persisted on the note *(Phase 5)*
- Suggest **tags** for a note via local LLM — suggest-only, never auto-attached *(Phase 5, in progress)*
- Ask questions in natural language, grounded in your own notes (RAG via Anthropic Claude) *(Phase 6)*

> **Status:** Phases 1–4 are complete — repo foundation, async MySQL + Notes CRUD API, JWT auth with per-user data isolation, and tags/collections/full-text search. **Phase 5 (local AI via Ollama) is in progress:** summarization works end-to-end against a real local model; tag suggestion is implemented with a fix in flight. RAG lands in Phase 6. See [Project Status](#project-status).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| API framework | FastAPI 0.115 + Uvicorn |
| Database | MySQL 8.4 (InnoDB, utf8mb4, FULLTEXT) |
| ORM / migrations | SQLAlchemy 2.x async (asyncmy) + Alembic |
| Auth | JWT (PyJWT) + Argon2 password hashing (pwdlib) |
| Local AI | Ollama (llama3.2:3b for summarization, nomic-embed-text for embeddings) |
| Cloud AI | Anthropic Claude (RAG Q&A) |
| Infrastructure | Docker + Docker Compose (dev/live + prod) |
| Package manager | uv |
| Linting / typing | ruff + mypy |
| CI/CD | GitHub Actions |

---

## Quickstart

Prerequisites: Docker Desktop running on Windows (or Docker + Docker Compose on Linux/macOS).

### 1. Clone and configure

```bash
git clone https://github.com/Zauwx/second-brain.git
cd second-brain
cp .env.example .env
```

Edit `.env` and set real values. The ones that matter for the current stack (api + MySQL + auth):

- `MYSQL_ROOT_PASSWORD`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — database credentials
- `DATABASE_URL` — must match the MySQL user/password/database above (host is `mysql`, the compose service name)
- `JWT_SECRET_KEY` — generate one with `python -c "import secrets; print(secrets.token_hex(32))"`

Anthropic and Ollama variables are only needed from Phase 5 onward.

### 2. Start the services

```bash
docker compose up -d --build
```

This starts three containers on an internal network: **api** (FastAPI, exposed on port 8000), **mysql** (MySQL 8.4, internal only), and **ollama** (local LLM runtime, internal only). The API waits for MySQL to pass its healthcheck.

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

Required on a fresh volume — the schema is not created automatically. Skipping this leaves every write returning `500` with `Table 'secondbrain.users' doesn't exist`.

### 4. Pull the local LLM model

```bash
docker compose exec ollama ollama pull llama3.2:3b
```

~2 GB, needed once per `ollama_data` volume. Only the AI endpoints depend on it; notes, tags, search, and auth work without it. Note that `GET /health` reports Ollama as `ok` once the *server* responds — it does not check whether a model is present.

### 5. Open the API

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the Swagger UI. From there you can:

1. `POST /auth/register` then `POST /auth/login` to obtain a JWT access token
2. Authorize in Swagger with the token
3. Create notes (`POST /notes/`), attach tags, and filter with `GET /notes?tag=python&tag=docker`
4. Generate a summary with `POST /ai/summarize` (persisted on the note) or get tag ideas with `POST /ai/suggest-tags` (suggest-only — never auto-attached)

A `200 OK` from `GET /health` confirms the API container is up. If Ollama is stopped, the AI endpoints return a clean `503` while all note operations keep working.

To wipe all data and start fresh: `docker compose down -v`.

---

## Architecture

The application follows a **domain-per-folder** layout inside `app/`:

```
app/
  main.py          # FastAPI app factory, lifespan hooks, router registration
  core/            # Settings (pydantic-settings), JWT/security helpers, shared dependencies
  database.py      # Async SQLAlchemy engine + session factory
  auth/            # JWT register/login/refresh/logout, User model, per-user isolation
  notes/           # Note CRUD — router, service, repository, schemas, ORM model
  tags/            # Tag many-to-many — same layered structure
  collections/     # Collection grouping — same layered structure
  search/          # Full-text search; semantic search (Phase 6)
  ai/              # Ollama local-LLM provider seam, summarize + suggest-tags (Phase 5);
                   #   Anthropic cloud RAG client (Phase 6)
```

Each domain uses the same layered structure: **router** (HTTP) → **service** (business logic) → **repository** (data access) → **model/schemas** (ORM + Pydantic).

Services run as Docker containers connected on an internal network:

- **api** — FastAPI application (Uvicorn in dev, Gunicorn in prod), exposed on port 8000
- **mysql** — MySQL 8.4, internal network only (not exposed to host)
- **ollama** — Local LLM runtime, internal network only *(added in Phase 5)*

Cloud LLM calls (Anthropic) go out over HTTPS directly from the API container. The API key is injected at runtime via `.env` — it never enters the Docker image.

---

## Project Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 — Repo Foundation | Git hygiene, project scaffold, Docker base, FastAPI skeleton, `GET /health` | ✅ Complete (2026-06-24) |
| 2 — Database + API Skeleton | Async MySQL, Alembic migrations, Note CRUD, OpenAPI docs, pagination, tests | ✅ Complete (2026-06-24) |
| 3 — Auth + Per-User Data Isolation | JWT auth with refresh tokens, per-user query isolation, cross-user access tests | ✅ Complete (2026-06-25) |
| 4 — Tags, Collections, Full-Text Search | Many-to-many tags, collections, MySQL FULLTEXT search, REST surface polish | ✅ Complete (2026-06-29) |
| 5 — Local AI (Ollama) | Ollama in Docker, LLM provider abstraction, auto-summarization, auto-tagging | 🚧 In progress |
| 6 — RAG Pipeline | Embedding pipeline, note chunks, cosine similarity, natural-language Q&A via Claude | ⏳ Planned |
| 7 — CI/CD Hardening + Portfolio Readiness | GitHub Actions lint/test/build/release, prod Compose, versioned images, secrets audit | ⏳ Planned |

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

# Start the stack with rebuild (dev)
docker compose up -d --build
```

---

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md)
for development setup, coding conventions, and the pull request process. By
participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Found a security issue? Please report it privately — see the [Security Policy](SECURITY.md).

---

## License

MIT — see [LICENSE](LICENSE).
