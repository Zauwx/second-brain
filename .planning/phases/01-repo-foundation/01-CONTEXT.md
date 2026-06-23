# Phase 1: Repo Foundation - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the repository with all **non-retrofittable hygiene** in place plus a minimal runnable FastAPI skeleton:
- Secrets excluded from git history forever (`.gitignore`, `.env.example`, never commit `.env`)
- Line endings fixed for Linux containers (`.gitattributes` forcing LF)
- A structured FastAPI skeleton that builds and runs in Docker with `GET /health` returning 200
- `uv`-managed Python project with ruff + mypy configured

Maps to requirement **OPS-05**. No application features (notes, auth, AI) — those start in Phase 2. This phase only establishes foundations that are painful or impossible to add safely after the first commit.

</domain>

<decisions>
## Implementation Decisions

### Repo Identity & Licensing
- **D-01:** Repo name is **`second-brain`** (a dedicated repo for the app). The local working directory stays `My-home-lab`, but the GitHub repo is named `second-brain`.
- **D-02:** Repo is **public** — this is an explicit portfolio goal; the commit history should be visible from the start.
- **D-03:** License is **MIT** — add a `LICENSE` file with the standard MIT text.
- **D-04:** README is **portfolio-grade** from Phase 1: title, one-line pitch, stack summary, a CI badge placeholder (wired in Phase 7), `docker compose up` quickstart, and a short architecture note. It gets enriched each phase.

### GitHub Remote
- **D-05:** Create the GitHub repo and push **now, in Phase 1**, via the `gh` CLI (`gh repo create second-brain --public --source=. --push` or equivalent). Begin the public commit history immediately.
- **D-06:** ⚠️ Precondition: `gh` must be authenticated. If `gh auth status` fails, the user must run `gh auth login` first (interactive — surface this in the plan as a manual step, do not assume it silently).

### Project Skeleton Scope
- **D-07:** Skeleton is **structured**, not bare. Lay down the domain-per-folder layout now so Phase 2 slots in cleanly:
  - `app/core/` — settings (`pydantic-settings`), config
  - `app/api/` — routers (with a `health` router as the first one)
  - `app/main.py` — FastAPI app assembly
  - placeholders/`__init__.py` for the domain folders the architecture research prescribed (notes/services/repositories) — empty but present
- **D-08:** Tooling: `pyproject.toml` managed by **`uv`**; **ruff** for lint/format and **mypy** for typing, both configured in `pyproject.toml`. `uv run ruff check app/` must pass clean on the skeleton.
- **D-09:** `/health` endpoint returns a simple JSON `{"status": "ok"}` with 200 — this is the smoke test for "Docker works end to end."

### Secrets & .env
- **D-10:** `.env.example` includes placeholder variables for all upcoming phases (so contributors and future-self see the full shape early), grouped and commented:
  - **DB (MySQL):** `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_ROOT_PASSWORD`, `DATABASE_URL`
  - **JWT:** `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`
  - **Cloud AI (Anthropic):** `ANTHROPIC_API_KEY`
  - **Ollama:** `OLLAMA_BASE_URL` (and model name vars)
- **D-11:** Real values live only in a gitignored `.env`. Settings are loaded via `pydantic-settings` (`BaseSettings`) in `app/core/`. `.env` must never enter git history (verified by `git log --all -- .env` returning nothing).

### Docker
- **D-12:** Base image **`python:3.12-slim`** (not Alpine — carried from project decisions). Multi-stage friendly, `uv` installed in the image. `docker-compose.yml` runs the api service for Phase 1 (mysql/ollama added in later phases). Do **not** bake secrets into image layers; use env files / `COPY` exclusions.

### Claude's Discretion
- Exact `.gitignore` contents (Python + Docker + IDE standards) — use sensible defaults including `.env`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `*.pyc`.
- Docker healthcheck wiring details and compose service naming.
- ruff/mypy strictness levels — start reasonable, can tighten later.
- Whether to include a `Makefile`/task runner — optional convenience.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level
- `.planning/PROJECT.md` — overall product context, constraints, key decisions
- `.planning/REQUIREMENTS.md` — OPS-05 is the only requirement in scope this phase
- `.planning/ROADMAP.md` §"Phase 1: Repo Foundation" — goal and the 4 success criteria this phase is judged against
- `.planning/STATE.md` §Decisions — locked stack choices (Python 3.12, `python:3.12-slim`, uv, asyncmy/pwdlib/PyJWT)

### Research (stack & pitfalls relevant to foundation)
- `.planning/research/STACK.md` — `uv`, FastAPI/uvicorn, ruff/mypy versions and rationale
- `.planning/research/ARCHITECTURE.md` — domain-per-folder layering (Router → Service → Repository), the layout the skeleton should seed; three-file Compose strategy (base + override + prod) to anticipate
- `.planning/research/PITFALLS.md` — Phase 0/1 pitfalls: CRLF→LF via `.gitattributes`, secrets-in-image / secrets-in-git, MySQL pinned `mysql:8.0` not MariaDB (for later), `utf8mb4` (later), Alembic-not-create_all (later)

No user-referenced external docs/ADRs were introduced during discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — this is the first phase of a greenfield project. The only existing files are `.planning/` planning docs and a freshly `git init`'d repo with no remote yet.

### Established Patterns
- None in code yet. The architecture research (`.planning/research/ARCHITECTURE.md`) prescribes the domain-per-folder pattern this skeleton should establish as the convention for all later phases.

### Integration Points
- This skeleton is the integration target for Phase 2 (Database + API Skeleton): `app/core` settings, `app/api` routers, and the Docker Compose file are where Phase 2 will add MySQL, Alembic, and the notes domain.

</code_context>

<specifics>
## Specific Ideas

- The README's `docker compose up` quickstart should actually work at the end of Phase 1 (hitting `/health` via Swagger at `http://localhost:8000/docs`) — the README's promise must match reality from day one.
- `.env.example` should be richer than Phase 1 strictly needs (includes DB/JWT/Anthropic/Ollama placeholders) so the full configuration surface is visible early and contributors aren't surprised later.

</specifics>

<deferred>
## Deferred Ideas

- Adding `mysql` and `ollama` services to Compose — Phase 2 (mysql) and Phase 5 (ollama).
- `docker-compose.prod.yml` and the prod gunicorn command — Phase 7 (CI/CD Hardening).
- CI workflow (`ci.yml`) that turns the README CI badge green — Phase 7. (A minimal lint-only CI *could* be introduced earlier as a learning exercise, but the full pipeline is the Phase 7 deliverable; keep Phase 1 local-tooling only unless the planner decides a tiny lint workflow adds learning value.)

None of the above is scope creep into Phase 1 — they are correctly sequenced into their own phases.

</deferred>

---

*Phase: 1-Repo Foundation*
*Context gathered: 2026-06-23*
