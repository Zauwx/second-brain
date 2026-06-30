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
- Group notes into **collections** *(Phase 4, in progress)*
- Keyword **full-text search** over titles and content via MySQL FULLTEXT *(Phase 4, in progress)*
- Multi-user with **JWT auth** (access + refresh tokens) and full **per-user data isolation**
- Ask questions in natural language, grounded in your own notes (RAG via Anthropic Claude) *(Phase 6)*
- Auto-generate summaries and suggested tags via a local LLM (Ollama) *(Phase 5)*

> **Status:** Phases 1–3 are complete — repo foundation, async MySQL + Notes CRUD API, and JWT auth with per-user data isolation. **Phase 4 (tags, collections, full-text search) is in progress.** AI features (Ollama, RAG) land in Phases 5–6. See [Project Status](#project-status).

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

This starts two containers on an internal network: **api** (FastAPI, exposed on port 8000) and **mysql** (MySQL 8.4, internal only). The API waits for MySQL to pass its healthcheck.

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Open the API

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the Swagger UI. From there you can:

1. `POST /auth/register` then `POST /auth/login` to obtain a JWT access token
2. Authorize in Swagger with the token
3. Create notes (`POST /notes/`), attach tags, and filter with `GET /notes?tag=python&tag=docker`

A `200 OK` from `GET /health` confirms the API container is up.

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
  collections/     # Collection grouping — same layered structure (Phase 4)
  search/          # Full-text search (Phase 4); semantic search (Phase 6)
  ai/              # Ollama (local LLM) and Anthropic (cloud RAG) clients (Phases 5–6)
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
| 4 — Tags, Collections, Full-Text Search | Many-to-many tags, collections, MySQL FULLTEXT search, REST surface polish | 🚧 In progress |
| 5 — Local AI (Ollama) | Ollama in Docker, LLM provider abstraction, auto-summarization, auto-tagging | ⏳ Planned |
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
