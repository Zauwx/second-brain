# Phase 1: Repo Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 1-Repo Foundation
**Areas discussed:** Repo identity & licensing, GitHub remote timing, Skeleton scope, Secrets & .env

---

## Repo Name / Framing

| Option | Description | Selected |
|--------|-------------|----------|
| second-brain | Dedicated repo for the app; clear portfolio name | ✓ |
| second-brain-api | Emphasizes API-first; good if multiple repos later | |
| my-home-lab (monorepo) | Repo = whole home lab, second-brain as first service | |

**User's choice:** second-brain
**Notes:** Local working dir stays `My-home-lab`; GitHub repo named `second-brain`.

## Repo Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Public | Portfolio goal; visible commit history | ✓ |
| Private first | Stay private, go public later | |

**User's choice:** Public

## License

| Option | Description | Selected |
|--------|-------------|----------|
| MIT | Permissive, standard, expected on portfolio | ✓ |
| Apache 2.0 | Permissive + explicit patent clause | |
| No license | All rights reserved by default | |

**User's choice:** MIT

## README Ambition

| Option | Description | Selected |
|--------|-------------|----------|
| Portfolio-grade | Title, pitch, stack, CI badge, quickstart, architecture | ✓ |
| Minimal | Title + description + how to run | |

**User's choice:** Portfolio-grade

---

## GitHub Remote Timing

| Option | Description | Selected |
|--------|-------------|----------|
| Now (Phase 1) | Create + push repo via gh CLI immediately | ✓ |
| Local first | Add remote later (e.g., Phase 7) | |

**User's choice:** Now (Phase 1)
**Notes:** Requires `gh` to be authenticated; `gh auth login` is a manual precondition.

## Skeleton Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Structured | FastAPI + /health + domain-per-folder layout + uv + ruff/mypy | ✓ |
| Minimal | Just main.py + /health + Dockerfile + compose | |

**User's choice:** Structured

## Secrets / .env Variables (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| DB (MySQL) | MYSQL_*, DATABASE_URL | ✓ |
| JWT | JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE | ✓ |
| Cloud API (Anthropic) | ANTHROPIC_API_KEY | ✓ |
| Ollama | OLLAMA_BASE_URL, models | ✓ |

**User's choice:** All four groups
**Notes:** `.env.example` seeds the full config surface early; real values stay in gitignored `.env`, loaded via pydantic-settings.

---

## Claude's Discretion

- `.gitignore` contents (Python/Docker/IDE standards, including `.env`)
- Docker healthcheck wiring and compose service naming
- ruff/mypy strictness levels (start reasonable)
- Optional Makefile/task runner

## Deferred Ideas

- mysql service in Compose → Phase 2
- ollama service in Compose → Phase 5
- docker-compose.prod.yml + gunicorn prod command → Phase 7
- Full CI workflow (ci.yml) to make README badge green → Phase 7
