# Architecture Research

**Domain:** Self-hosted personal knowledge base — FastAPI REST API + MySQL + Ollama (local LLM) + cloud LLM (RAG), fully containerized, Windows/Docker Desktop, CI/CD via GitHub Actions
**Researched:** 2026-06-23
**Confidence:** HIGH (multiple authoritative sources cross-verified)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  HTTP clients: curl / Swagger UI / any frontend (port 8000)     │    │
│  └────────────────────────────┬────────────────────────────────────┘    │
└───────────────────────────────│─────────────────────────────────────────┘
                                │ HTTP/REST
┌───────────────────────────────▼─────────────────────────────────────────┐
│                        API CONTAINER  (api)                              │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI application                                              │   │
│  │  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │   │
│  │  │  Routers  │  │ Services  │  │  Repos   │  │  AI Services │  │   │
│  │  │ /notes    │  │ NotesSvc  │  │ NotesRepo│  │ LLMRouter    │  │   │
│  │  │ /tags     │  │ AuthSvc   │  │ TagsRepo │  │ OllamaClient │  │   │
│  │  │ /search   │  │ RAGSvc    │  │ UserRepo │  │ CloudClient  │  │   │
│  │  │ /ai       │  │ EmbedSvc  │  │ EmbedRepo│  │ EmbedSvc     │  │   │
│  │  │ /auth     │  └───────────┘  └──────────┘  └──────────────┘  │   │
│  │  └───────────┘                                                   │   │
│  │  ┌───────────────────────────────────────────────────────────┐  │   │
│  │  │  Core: config (pydantic-settings), deps, auth (JWT),      │  │   │
│  │  │  schemas (Pydantic), exceptions, middleware                │  │   │
│  │  └───────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└───────────┬───────────────────────────────────────┬─────────────────────┘
            │ aiomysql / SQLAlchemy async            │ HTTP  ollama-python
┌───────────▼────────────────┐         ┌────────────▼──────────────────────┐
│   DB CONTAINER  (mysql)    │         │  LLM CONTAINER  (ollama)          │
│   MySQL 8.4 / InnoDB       │         │  Ollama  :11434                   │
│   utf8mb4  /  FULLTEXT     │         │  llama3.2 (summarise / tag)       │
│   Alembic migrations       │         │  nomic-embed-text (embeddings)    │
└────────────────────────────┘         └───────────────────────────────────┘
                                                         (internal network only)
                                       ┌───────────────────────────────────┐
                                       │  CLOUD LLM API  (external)        │
                                       │  Anthropic Claude / OpenAI GPT    │
                                       │  Used only for RAG Q&A            │
                                       └───────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| **Routers** | HTTP endpoints: parse request, call service, return response. Zero business logic. | FastAPI `APIRouter`, one file per domain (`notes.py`, `auth.py`, `ai.py`) |
| **Services** | Business logic: orchestrate repos and AI clients. No HTTP concerns. | Plain Python classes injected via FastAPI `Depends()` |
| **Repositories** | Data access: all SQL lives here, nothing else. | Async SQLAlchemy 2.0 + `AsyncSession`; one class per entity |
| **Schemas** | Request/response contracts. | Pydantic v2 models — separate `Create`, `Update`, `Read` schemas per domain |
| **Core / Config** | App-wide settings, DI wiring, JWT helpers, middleware. | `pydantic-settings` `BaseSettings`, `.env` files, 12-factor |
| **LLM Router** | Decides which LLM backend handles a task (local vs cloud). | Thin abstraction class with `BaseLLMClient` ABC, `OllamaClient`, `CloudLLMClient` implementations |
| **Embed Service** | Produces and stores vector embeddings for chunks; performs ANN search. | Calls Ollama `nomic-embed-text`; stores JSON/BLOB in MySQL `note_chunks` table |
| **MySQL** | Relational store: notes, tags, collections, users, chunks + embeddings. | MySQL 8.4, InnoDB, utf8mb4, FULLTEXT on `content`, managed by Alembic |
| **Ollama** | Local inference: summarisation, tag suggestion, embedding generation. | Ollama container; models persisted in a named volume |
| **Cloud LLM API** | Heavy reasoning: RAG Q&A answer generation with citations. | HTTPS to Anthropic/OpenAI; API key in env secret, never in image |

---

## Recommended Project Structure

```
second-brain/
├── app/
│   ├── main.py                  # FastAPI app factory, lifespan, router registration
│   ├── config.py                # Global pydantic-settings (DATABASE_URL, JWT_SECRET, LLM keys)
│   ├── database.py              # Async engine, session factory, Base declarative
│   ├── dependencies.py          # Shared DI: get_db, get_current_user
│   │
│   ├── notes/
│   │   ├── router.py            # GET/POST/PUT/DELETE /notes
│   │   ├── schemas.py           # NoteCreate, NoteUpdate, NoteRead
│   │   ├── models.py            # SQLAlchemy Note ORM model
│   │   ├── service.py           # NoteService (CRUD + search orchestration)
│   │   └── repository.py        # NoteRepository (all SQL for notes)
│   │
│   ├── tags/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py            # Tag, NoteTag (join table)
│   │   ├── service.py
│   │   └── repository.py
│   │
│   ├── collections/
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py            # Collection, NoteCollection (join table)
│   │   ├── service.py
│   │   └── repository.py
│   │
│   ├── auth/
│   │   ├── router.py            # POST /auth/register, /auth/login, /auth/refresh
│   │   ├── schemas.py           # UserCreate, TokenResponse
│   │   ├── models.py            # User ORM model
│   │   ├── service.py           # AuthService: hash password, issue JWT
│   │   ├── repository.py        # UserRepository
│   │   └── dependencies.py      # parse_jwt_data, get_current_user (reusable)
│   │
│   ├── ai/
│   │   ├── router.py            # POST /ai/summarise, /ai/suggest-tags, /ai/ask
│   │   ├── schemas.py           # SummariseRequest, AskRequest, AskResponse
│   │   ├── llm_router.py        # LLMRouter: route task -> OllamaClient | CloudLLMClient
│   │   ├── ollama_client.py     # OllamaClient wrapping ollama-python / httpx
│   │   ├── cloud_client.py      # CloudLLMClient wrapping Anthropic/OpenAI SDK
│   │   ├── embed_service.py     # chunk(), embed(), store_chunks(), similarity_search()
│   │   └── rag_service.py       # RAGService: orchestrate retrieve -> prompt -> answer
│   │
│   └── search/
│       ├── router.py            # GET /search?q=
│       ├── schemas.py
│       └── service.py           # Full-text MATCH AGAINST + cosine similarity merge
│
├── alembic/
│   ├── env.py
│   └── versions/               # Migration scripts (static, reversible)
│
├── tests/
│   ├── conftest.py              # httpx.AsyncClient, dependency_overrides, test DB
│   ├── test_notes.py
│   ├── test_auth.py
│   └── test_ai.py
│
├── docker/
│   ├── Dockerfile               # Production image
│   └── Dockerfile.dev           # Dev image (or override CMD in compose)
│
├── docker-compose.yml           # Base: services, networks, named volumes
├── docker-compose.override.yml  # Dev additions: bind mounts, hot-reload, debug ports
├── docker-compose.prod.yml      # Prod additions: resource limits, gunicorn workers, no mounts
├── .env.example                 # Template — committed
├── .env                         # Actual secrets — gitignored
├── .env.prod                    # Prod env template — gitignored or in CI secrets
├── pyproject.toml               # deps + ruff + pytest config
└── .github/
    └── workflows/
        ├── ci.yml               # lint -> test -> build image
        └── release.yml          # tag push -> build + push Docker Hub / GHCR
```

### Structure Rationale

- **Domain-per-folder (not file-type-per-folder):** Adding a new domain (e.g., `sources/`) means touching one folder, not five scattered directories. Follows the Netflix Dispatch pattern endorsed by the FastAPI best-practices repository.
- **`ai/` as a first-class domain:** LLM features span multiple HTTP endpoints and have their own clients and services; they deserve isolation from `notes/`.
- **`docker/` subdirectory:** Keeps Dockerfiles out of project root clutter while remaining discoverable.
- **`alembic/` at root level:** Convention; Alembic needs to import `app.database.Base`.

---

## Architectural Patterns

### Pattern 1: Domain-Scoped Dependency Injection

**What:** Each domain exposes a `get_service()` function that FastAPI resolves per request. Session, settings, and auth are injected into services, not imported globally.

**When to use:** Every endpoint. This is the standard FastAPI pattern.

**Trade-offs:** Slightly verbose for small apps; pays off immediately when you need to override dependencies in tests.

**Example:**
```python
# app/notes/dependencies.py
async def get_note_service(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteService:
    return NoteService(NoteRepository(db), current_user)

# app/notes/router.py
@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, svc: NoteService = Depends(get_note_service)):
    return await svc.get_or_404(note_id)
```

### Pattern 2: LLM Provider Abstraction (Router Pattern)

**What:** A `BaseLLMClient` ABC defines the contract (`complete(prompt) -> str`). `OllamaClient` and `CloudLLMClient` implement it. `LLMRouter` selects the right backend based on task type.

**When to use:** Immediately — even if you only have Ollama at first. Adding cloud later requires zero changes to callers.

**Trade-offs:** One extra indirection layer. Worth it for this project since switching providers is an explicit learning goal.

**Example:**
```python
# app/ai/llm_router.py
class LLMRouter:
    LOCAL_TASKS = {"summarise", "suggest_tags", "embed"}
    CLOUD_TASKS = {"rag_answer"}

    def get_client(self, task: str) -> BaseLLMClient:
        if task in self.LOCAL_TASKS:
            return self._ollama
        return self._cloud
```

### Pattern 3: Repository — No Raw SQL in Services

**What:** All SQLAlchemy queries live in `*Repository` classes. Services call repository methods and apply business rules. Routers call services.

**When to use:** Every data access operation.

**Trade-offs:** Extra layer for very simple CRUD. The payoff is testability: swap `NoteRepository` with a fake in tests, no DB required.

**Example:**
```python
# app/notes/repository.py
class NoteRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_user(self, user_id: int) -> list[Note]:
        result = await self._session.execute(
            select(Note).where(Note.user_id == user_id).order_by(Note.created_at.desc())
        )
        return result.scalars().all()
```

### Pattern 4: 12-Factor Config via pydantic-settings

**What:** All configuration comes from environment variables. `pydantic-settings` reads them, validates them, and makes them available as typed attributes. No config is hard-coded in application code.

**When to use:** From day one. Retrofitting later is painful.

**Trade-offs:** None meaningful at this scale.

**Example:**
```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    CLOUD_LLM_API_KEY: str = ""
    CLOUD_LLM_MODEL: str = "claude-3-5-haiku-20241022"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Data Flow

### Standard CRUD Request Flow

```
HTTP Client
    │ POST /notes  {title, content, source_url}
    ▼
Router (notes/router.py)
    │ validate body with NoteCreate schema
    │ call svc.create_note(data, current_user)
    ▼
NoteService (notes/service.py)
    │ apply business rules (strip whitespace, set user_id)
    │ call repo.create(note)
    ▼
NoteRepository (notes/repository.py)
    │ INSERT INTO notes ...
    ▼
MySQL (InnoDB)
    │ row inserted, id returned
    ▼
NoteRepository → NoteService → Router
    │ return NoteRead schema (serialised by Pydantic)
    ▼
HTTP Client  201 Created  {id, title, content, created_at, ...}
```

### RAG Pipeline — Full Data Flow

```
INGEST PATH (triggered by note create / explicit ingest endpoint)
───────────────────────────────────────────────────────────────────
Note saved to MySQL
    │
    ▼
EmbedService.ingest_note(note)
    │ 1. chunk(note.content, max_tokens=400, overlap=50)
    │    → list[str]  (RecursiveCharacterSplitter or simple sliding window)
    ▼
    │ 2. For each chunk:
    │    OllamaClient.embed(chunk, model="nomic-embed-text")
    │    → list[float]  (768-dim vector)
    ▼
    │ 3. EmbedRepository.store_chunk(note_id, chunk_text, embedding_json)
    │    INSERT INTO note_chunks (note_id, chunk_text, embedding)
    │    embedding stored as JSON array (suitable for personal scale <50k notes)
    ▼
MySQL note_chunks table (note_id FK, chunk_text TEXT, embedding JSON)


QUERY / RAG PATH (POST /ai/ask  {question})
───────────────────────────────────────────────────────────────────
HTTP Request: {question: "What did I learn about Docker networking?"}
    │
    ▼
RAGService.answer(question, current_user)
    │ 1. OllamaClient.embed(question, model="nomic-embed-text")
    │    → query_vector: list[float]
    ▼
    │ 2. EmbedRepository.similarity_search(query_vector, user_id, top_k=5)
    │    SELECT note_id, chunk_text, embedding FROM note_chunks
    │    JOIN notes ON notes.id = note_chunks.note_id
    │    WHERE notes.user_id = :user_id
    │    → compute cosine similarity in Python (acceptable at personal scale)
    │    → return top 5 chunks with note metadata
    ▼
    │ 3. Build prompt:
    │    CONTEXT: [chunk1] [chunk2] ... [chunk5]
    │    QUESTION: {question}
    │    INSTRUCTION: Answer using only the context. Cite note IDs.
    ▼
    │ 4. CloudLLMClient.complete(prompt)
    │    → HTTPS to Anthropic/OpenAI API
    │    → answer: str  (with inline citations)
    ▼
    │ 5. Return AskResponse {answer, source_note_ids, chunks_used}
    ▼
HTTP Client  200 OK  {answer: "...", sources: [note_id_3, note_id_7]}
```

### Local LLM Tasks Flow (Summarise / Tag)

```
POST /ai/summarise  {note_id}
    │
    ▼
AIRouter → LLMRouter.get_client("summarise") → OllamaClient
    │ POST http://ollama:11434/api/generate
    │ {model: "llama3.2", prompt: "Summarise: {note.content}"}
    ▼
Ollama container (internal network, not exposed to host)
    │ response stream → collected as string
    ▼
AIRouter → update note.summary in MySQL
    │
    ▼
HTTP Client  200 OK  {summary: "..."}
```

### Key Data Flows Summary

1. **Note creation triggers async ingest:** after the note is persisted, a background task (FastAPI `BackgroundTasks`) chunks and embeds it — the HTTP response is not blocked.
2. **Embeddings live in MySQL:** for personal scale (< 50k chunks), cosine similarity computed in Python on retrieved rows is fast enough. No separate vector DB needed.
3. **Ollama is never on the public network:** only the `api` container calls `http://ollama:11434` over the internal Docker network.
4. **Cloud LLM key never touches MySQL or logs:** it is injected as an environment variable, read by `Settings`, and used only in `CloudLLMClient`.

---

## MySQL Schema Skeleton

```sql
-- Users (multi-tenant isolation anchor)
CREATE TABLE users (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) NOT NULL UNIQUE,
    hashed_pw   VARCHAR(255) NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Notes (core entity)
CREATE TABLE notes (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    title       VARCHAR(512),
    content     LONGTEXT NOT NULL,
    source_url  VARCHAR(2048),
    summary     TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FULLTEXT KEY ft_content (title, content)   -- enables MATCH AGAINST search
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tags (normalised dictionary)
CREATE TABLE tags (
    id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    name    VARCHAR(128) NOT NULL,
    UNIQUE KEY uq_user_tag (user_id, name),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Note-Tag join (many-to-many)
CREATE TABLE note_tags (
    note_id INT UNSIGNED NOT NULL,
    tag_id  INT UNSIGNED NOT NULL,
    PRIMARY KEY (note_id, tag_id),
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)  REFERENCES tags(id)  ON DELETE CASCADE
) ENGINE=InnoDB;

-- Collections
CREATE TABLE collections (
    id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    name    VARCHAR(255) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Note-Collection join (many-to-many)
CREATE TABLE note_collections (
    note_id       INT UNSIGNED NOT NULL,
    collection_id INT UNSIGNED NOT NULL,
    PRIMARY KEY (note_id, collection_id),
    FOREIGN KEY (note_id)       REFERENCES notes(id)       ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Chunk + Embedding store (RAG)
CREATE TABLE note_chunks (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    note_id    INT UNSIGNED NOT NULL,
    chunk_idx  SMALLINT UNSIGNED NOT NULL,      -- position within note
    chunk_text TEXT NOT NULL,
    embedding  JSON NOT NULL,                   -- float array, e.g. [0.12, -0.34, ...]
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    INDEX idx_chunk_note (note_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Indexing notes:**
- `FULLTEXT KEY ft_content` on `notes(title, content)` enables `MATCH (title, content) AGAINST (:q IN BOOLEAN MODE)` for keyword search. This index only works with InnoDB and requires `innodb_ft_enable_stopword` awareness.
- `embedding` stored as `JSON` column is brute-force scanned at query time — acceptable for personal scale; revisit if chunk count exceeds ~100k.
- All tables use `utf8mb4 / utf8mb4_unicode_ci` for full emoji and multilingual support.

---

## Container Topology (Docker Compose)

### Services

```
docker-compose.yml (base — shared by all environments)
├── api         → builds ./docker/Dockerfile, port 8000:8000 (on host)
│                 depends_on: mysql (condition: service_healthy)
│                 depends_on: ollama (condition: service_started)
│                 networks: [backend]
│
├── mysql       → image: mysql:8.4
│                 volumes: mysql_data:/var/lib/mysql
│                 volumes: ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
│                 healthcheck: mysqladmin ping -h localhost
│                 networks: [backend]
│                 NO port mapping (not exposed to host)
│
└── ollama      → image: ollama/ollama:latest
                  volumes: ollama_data:/root/.ollama
                  healthcheck: curl -f http://localhost:11434/
                  networks: [backend]
                  NO port mapping in prod (optional 11434:11434 in dev for direct access)

networks:
  backend:
    driver: bridge      # internal — api, mysql, ollama talk by service name

volumes:
  mysql_data:
  ollama_data:
```

### Dev Environment (docker-compose.override.yml)

Applied automatically when running `docker compose up` (Compose merges base + override):

```yaml
# docker-compose.override.yml
services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app                    # bind mount: code changes reflected instantly
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=debug
    ports:
      - "8000:8000"

  mysql:
    ports:
      - "3306:3306"               # expose to host for DB client (TablePlus, DBeaver)

  ollama:
    ports:
      - "11434:11434"             # expose to host for curl testing
```

Key dev differences:
- `--reload` flag on uvicorn — auto-restart on code change
- Bind mount of `.:/app` — no image rebuild cycle
- All ports exposed to host — direct debugging access
- `DEBUG=true`, verbose logging

### Prod Environment (docker-compose.prod.yml)

Invoked explicitly: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

```yaml
# docker-compose.prod.yml
services:
  api:
    image: ghcr.io/your-org/second-brain:${VERSION}   # pre-built, tagged image
    command: >
      gunicorn -w 4 -k uvicorn.workers.UvicornWorker
               app.main:app --bind 0.0.0.0:8000
    env_file:
      - .env.prod
    deploy:
      resources:
        limits:
          memory: 1G
    restart: unless-stopped
    # NO bind mounts — image is immutable
    # NO ports except through reverse proxy (Nginx/Traefik)

  mysql:
    # NO host port exposure
    restart: unless-stopped

  ollama:
    # NO host port exposure
    restart: unless-stopped
```

Key prod differences vs dev:

| Concern | Dev | Prod |
|---------|-----|------|
| Server | `uvicorn --reload` | `gunicorn -w 4 -k UvicornWorker` |
| Code | Bind-mounted from host | Baked into image at build time |
| Ports | All exposed to host | Only API behind reverse proxy |
| Logging | DEBUG, verbose | INFO/WARNING, structured JSON |
| Image | Built locally on-the-fly | Tagged immutable image from CI |
| Seed data | `docker-entrypoint-initdb.d/` script | Schema-only migration via Alembic |
| Secrets | `.env` file on dev machine | `.env.prod` not in repo; injected by CI/CD or secrets manager |

---

## CI/CD Shape (GitHub Actions)

### Workflow: `ci.yml` — runs on every push and PR

```
Trigger: push to any branch / pull_request to main
    │
    ▼
Job: lint
    │ ruff check app/ tests/
    │ ruff format --check app/ tests/
    ▼
Job: test  (needs: lint)
    │ spin up mysql:8.4 service container (GitHub Actions service)
    │ pytest tests/ --asyncio-mode=auto --cov=app
    ▼
Job: build  (needs: test, only on main or tag)
    │ docker build -t ghcr.io/org/second-brain:${{ github.sha }} .
    │ docker push (if main branch or semver tag)
```

### Workflow: `release.yml` — runs on semver tag push (`v*.*.*`)

```
Trigger: push tag matching v*.*.*
    │
    ▼
Job: release
    │ docker build --build-arg VERSION=${{ github.ref_name }}
    │ docker tag :sha → :v1.2.3
    │ docker tag :sha → :latest
    │ docker push all tags to GHCR
    │ gh release create $TAG --generate-notes
```

### Versioning strategy

- **Branch:** `main` — stable; CI must pass before merge
- **Tags:** `v1.0.0`, `v1.1.0` etc. follow semver; created manually after milestone completion
- **Image tags:** `:sha-abcdef` for every main build; `:v1.2.3` and `:latest` on release
- **No auto-bump bots** — tag creation is intentional, tied to learning milestones

### Secrets in CI

| Secret Name | Where Used |
|-------------|-----------|
| `GHCR_TOKEN` | `docker push` to GitHub Container Registry |
| `CLOUD_LLM_API_KEY` | Integration tests (optional — can be skipped in CI) |
| `JWT_SECRET` | Test environment via GitHub Actions env vars |

---

## Build Order (Phase Dependencies)

The correct build order is driven by two rules: (a) you cannot test what does not exist, (b) AI features require notes data and auth to be meaningful.

```
Phase 1 — DB + API Skeleton
    MySQL schema (Alembic baseline migration)
    FastAPI app factory, config, database session
    Notes CRUD (no auth — all notes public for now)
    Manual Swagger testing
    Docker Compose base (api + mysql)
    → Deliverable: notes CRUD works via Swagger in Docker

Phase 2 — Auth + Data Isolation
    User model + UserRepository
    JWT issue/verify (auth router)
    current_user dependency injected into notes endpoints
    User isolation enforced in all queries
    → Deliverable: multi-user API, each user sees only their notes

Phase 3 — Tags, Collections, Full-text Search
    Tags many-to-many, Collections many-to-many
    FULLTEXT MATCH AGAINST search endpoint
    → Deliverable: full REST surface, documented via Swagger

Phase 4 — Local AI (Ollama)
    Ollama service added to Docker Compose
    OllamaClient + LLMRouter skeleton
    /ai/summarise and /ai/suggest-tags endpoints
    → Deliverable: local LLM features working end-to-end in Docker

Phase 5 — RAG (Embeddings + Cloud LLM)
    note_chunks table (Alembic migration)
    EmbedService: chunk + embed via Ollama nomic-embed-text
    BackgroundTasks hook on note create
    RAGService: similarity search + cloud LLM prompt
    /ai/ask endpoint
    → Deliverable: natural language Q&A over personal notes

Phase 6 — CI/CD Hardening
    GitHub Actions: lint + test + build
    Docker image tagging strategy
    Prod compose file
    Secrets management audit
    → Deliverable: green CI, pushable Docker image, portfolio-ready repo
```

Dependencies between phases:

```
Phase 1 (DB + Skeleton)
    └── Phase 2 (Auth)          ← requires User model
            └── Phase 3 (Tags/Search)  ← requires user isolation
                    └── Phase 4 (Ollama)    ← requires notes to summarise
                            └── Phase 5 (RAG)    ← requires Ollama for embeddings
                                    └── Phase 6 (CI/CD) ← requires working app
```

Phase 6 (CI/CD) can be partially started after Phase 1 (lint + basic test pipeline), but the Docker build and push steps only become meaningful after Phase 5.

---

## Scaling Considerations

| Scale | Situation | Architecture Adjustment |
|-------|-----------|-------------------------|
| 1 user (self) | Home lab | Current design is right-sized. JSON embedding scan is fast for < 10k chunks. |
| 10 users | Friends / small team | Add indexes on `note_chunks.note_id`. Consider connection pooling tuning on SQLAlchemy pool size. |
| 100+ users | If this ever grows | Replace JSON cosine scan with pgvector/Qdrant. Add Redis for JWT token denylist. Separate `embed` into a worker queue (Celery + Redis). |

The first bottleneck will be the in-Python cosine similarity loop over note_chunks — acceptable until chunk count exceeds ~20–50k rows, then it becomes noticeably slow.

The second bottleneck is Ollama single-threaded inference — it queues requests; for > 5 concurrent users the embed/summarise wait becomes unacceptable. At that point, queue embedding jobs asynchronously.

---

## Anti-Patterns

### Anti-Pattern 1: Business Logic in Routers

**What people do:** Put database queries or LLM calls directly inside the `@router.get` handler function.

**Why it's wrong:** Untestable without HTTP; logic gets duplicated when adding a background job or CLI command that needs the same operation.

**Do this instead:** Router calls service; service calls repository/LLM client. Test the service in isolation using `dependency_overrides`.

### Anti-Pattern 2: Monolithic `models.py` and `schemas.py`

**What people do:** Put every ORM model in one `models.py` and every Pydantic schema in one `schemas.py` at the app root.

**Why it's wrong:** File grows to 800 lines; hard to navigate; circular imports appear as you add relationships.

**Do this instead:** One `models.py` per domain folder. `database.py` holds only `Base` and the engine. Each domain imports `Base` from `database.py`.

### Anti-Pattern 3: Storing API Keys in Docker Images

**What people do:** `ENV CLOUD_LLM_API_KEY=sk-...` in a Dockerfile, or hardcode in `docker-compose.yml`.

**Why it's wrong:** The key is baked into every image layer and visible to anyone who pulls it.

**Do this instead:** Use `env_file: .env.prod` in compose (gitignored) or inject from GitHub Actions Secrets at CI build time. The application reads it via `pydantic-settings`; the image knows nothing.

### Anti-Pattern 4: Running Alembic Migrations Inside the Application Startup

**What people do:** `alembic upgrade head` inside `main.py` lifespan, so migrations run every time the API starts.

**Why it's wrong:** If two API replicas start simultaneously, both run migrations — race condition. Migrations that take > 30s cause the health check to time out.

**Do this instead:** Run `alembic upgrade head` as a one-shot Docker Compose `init` service or a pre-deploy step in CI/CD before the API container starts.

### Anti-Pattern 5: One Compose File for Everything

**What people do:** A single `docker-compose.yml` that contains both `--reload` dev command and prod resource limits, with a giant `if` comment explaining which lines to uncomment.

**Why it's wrong:** Mistakes happen; someone ships the dev image to prod. The config is unreadable.

**Do this instead:** Base `docker-compose.yml` + `docker-compose.override.yml` (dev, auto-applied) + `docker-compose.prod.yml` (prod, explicit). Compose merge is designed for exactly this pattern.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Ollama (container) | HTTP via `ollama-python` client or raw `httpx` to `http://ollama:11434` | Use Docker service name, not `localhost`. Model must be pulled before first use — add an entrypoint script or a Compose `ollama-init` one-shot service. |
| Cloud LLM API (Anthropic/OpenAI) | Official Python SDK (anthropic / openai) over HTTPS | Key via env var. Rate-limit errors should be caught in `CloudLLMClient` and surfaced as 503 to the caller, not 500. |
| MySQL | SQLAlchemy 2.0 async engine with `aiomysql` driver | Connection string: `mysql+aiomysql://user:pass@mysql:3306/db`. Use `pool_pre_ping=True` to detect stale connections after MySQL restart. |
| GitHub Container Registry | `docker login ghcr.io` + `docker push` in CI | Image naming: `ghcr.io/{github_username}/second-brain:{tag}`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Router ↔ Service | Direct Python function call (same process) | No serialisation overhead; easy to mock. |
| Service ↔ Repository | Direct Python function call | Session passed in via constructor DI. |
| Service ↔ LLMRouter | Direct Python call | LLMRouter is a singleton injected via `Depends`. |
| API container ↔ MySQL | TCP on Docker `backend` network, port 3306 | MySQL not exposed to host in prod. |
| API container ↔ Ollama | HTTP on Docker `backend` network, port 11434 | Ollama not exposed to host in prod. |
| EmbedService ↔ note_chunks | Via EmbedRepository (SQLAlchemy) | Embedding written in background task; never blocks HTTP response. |

---

## Sources

- FastAPI best practices (project structure, DI patterns): [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
- FastAPI official Docker deployment guide: [fastapi.tiangolo.com/deployment/docker](https://fastapi.tiangolo.com/deployment/docker/)
- Docker Compose FastAPI + MySQL + Ollama RAG reference: [Medium — Docker-FastAPI: Local AI-RAG with LangGraph, Ollama and MySQL](https://medium.com/@ion.stefanache0/docker-fastapi-rag-with-langgraph-faiss-and-mysql-9ca64d00abc8)
- Ollama production Docker Compose: [SitePoint — Ollama Production Deployment](https://www.sitepoint.com/ollama-local-llm-production-deployment-docker/)
- LiteLLM provider abstraction: [Medium — A gentle introduction to LiteLLM](https://medium.com/mitb-for-all/a-gentle-introduction-to-litellm-649d48a0c2c7)
- MySQL FULLTEXT indexes: [MySQL 8.4 Reference Manual — InnoDB Full-Text Indexes](https://dev.mysql.com/doc/refman/8.4/en/innodb-fulltext-index.html)
- MySQL vector/embedding storage: [Medium — Enhancing MySQL Searches with Vector Embeddings](https://medium.com/@stephenc211/enhancing-mysql-searches-with-vector-embeddings-11f183932851)
- SQLAlchemy 2.0 async patterns: [dev-faizan.medium.com — FastAPI + SQLAlchemy 2.0](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843)
- GitHub Actions CI for FastAPI: [PyImageSearch — Enhancing GitHub Actions CI for FastAPI](https://pyimagesearch.com/2024/11/04/enhancing-github-actions-ci-for-fastapi-build-test-and-publish/)
- FastAPI service layer architecture: [Medium — Building Production-Ready FastAPI Applications](https://medium.com/@abhinav.dobhal/building-production-ready-fastapi-applications-with-service-layer-architecture-in-2025-f3af8a6ac563)

---

*Architecture research for: Second Brain — personal knowledge base with hybrid AI*
*Researched: 2026-06-23*
