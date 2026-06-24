---
phase: "01-repo-foundation"
plan: "01"
subsystem: "repository-hygiene"
tags: [gitignore, gitattributes, env-template, license, readme, secrets-exclusion, lf-enforcement]

dependency_graph:
  requires: []
  provides:
    - ".gitignore with .env exclusion rule (secrets never in git history)"
    - ".gitattributes with LF enforcement for Linux container compatibility"
    - ".env.example with grouped placeholders for all phases (MySQL/JWT/Anthropic/Ollama)"
    - "MIT LICENSE (2026)"
    - "portfolio-grade README with docker compose up quickstart and /health smoke test"
  affects:
    - "All future commits — .gitattributes enforces LF from this point forward"
    - "All future phases — .env.example shows full configuration surface early"
    - "Plan 03 (GitHub push) — README, LICENSE, and hygiene files are the first public history"

tech_stack:
  added: []
  patterns:
    - ".env / .env.example split (secrets local, template committed)"
    - "gitattributes LF enforcement pattern (Pitfall 15 mitigation)"

key_files:
  created:
    - path: ".gitignore"
      role: "Excludes .env and all Python/Docker/IDE generated artifacts from git tracking"
    - path: ".gitattributes"
      role: "Forces LF line endings globally; explicit eol=lf for .sh, .py, Dockerfile, docker-compose*.yml"
    - path: ".env.example"
      role: "Committed template with placeholder variables for all phases (MySQL, JWT, Anthropic, Ollama)"
    - path: "LICENSE"
      role: "MIT license 2026"
    - path: "README.md"
      role: "Portfolio README: pitch, stack, CI badge placeholder, docker compose up quickstart, architecture note, phase status table"
  modified: []

decisions:
  - "LF enforcement via .gitattributes before any code exists — impossible to add safely after CRLF files are committed"
  - ".env excluded with bare .env line (not .env*) so .env.example is never accidentally ignored"
  - "!.env.example negation in .gitignore as belt-and-suspenders even though the bare .env rule wouldn't catch it"
  - "README CI badge added as commented placeholder — not wired until Phase 7 (accurate, not fabricated)"
  - "README quickstart describes Phase 1 reality only (GET /health) — no undelivered features claimed"

metrics:
  duration_minutes: 3
  completed_date: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 0
---

# Phase 01 Plan 01: Repository Hygiene — Summary

Non-retrofittable repository hygiene layer laid down before any application code: secrets exclusion (.gitignore), LF line-ending enforcement (.gitattributes), committed env template (.env.example), MIT license, and a portfolio-grade README with an accurate docker compose up quickstart.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .gitignore and .gitattributes | 4553031 | `.gitignore`, `.gitattributes` |
| 2 | Create .env.example with all-phase placeholders | eaa2127 | `.env.example` |
| 3 | Create MIT LICENSE and portfolio-grade README | aea78e5 | `LICENSE`, `README.md` |

## What Was Built

**Task 1 — .gitignore and .gitattributes:**
- `.gitignore` covers Python (`__pycache__/`, `*.pyc`, `.venv/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`), secrets (`.env`, `.env.prod`), IDE (`.idea/`, `.vscode/`), and OS artifacts. `uv.lock` is intentionally NOT ignored (must be committed for reproducible installs). A `!.env.example` negation ensures the template is always tracked.
- `.gitattributes` sets `* text=auto eol=lf` globally plus explicit `eol=lf` for `.sh`, `.py`, `Dockerfile`, `Dockerfile.*`, `docker-compose*.yml`, and all config/doc file types. Binary files (images, fonts) are marked as `binary` to skip EOL processing.

**Task 2 — .env.example:**
Four commented groups covering all upcoming phases:
- **DB (MySQL):** `MYSQL_ROOT_PASSWORD`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `DATABASE_URL` (asyncmy DSN shape: `mysql+asyncmy://user:pass@mysql:3306/db?charset=utf8mb4`)
- **JWT:** `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS`, `JWT_ALGORITHM`
- **Cloud AI (Anthropic):** `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL=claude-sonnet-4-5`
- **Ollama:** `OLLAMA_BASE_URL=http://ollama:11434`, `OLLAMA_CHAT_MODEL=llama3.2:3b`, `OLLAMA_EMBED_MODEL=nomic-embed-text`
- **App:** `ENVIRONMENT`, `LOG_LEVEL`

All values are obvious placeholders (`changeme-*`, `your-*-here`). No real `.env` file created.

**Task 3 — LICENSE and README:**
- `LICENSE`: Standard MIT text, year 2026.
- `README.md` (146 lines): one-line pitch, stack table (Python 3.12, FastAPI, MySQL 8.4, SQLAlchemy async, Alembic, PyJWT, pwdlib, Ollama, Anthropic Claude, Docker, uv, ruff, mypy, GitHub Actions), commented CI badge placeholder (wired Phase 7), `docker compose up` quickstart with step-by-step instructions through `GET /health → 200`, architecture note with domain-per-folder layout and three-container topology, phase status table, development commands.

## Verification Results

All plan verification commands pass:

```
PASS: .env in .gitignore (bare .env line)
PASS: eol=lf present in .gitattributes
PASS: .env.example has all 4 groups (MYSQL_USER, JWT_SECRET_KEY, ANTHROPIC_API_KEY, OLLAMA_BASE_URL)
PASS: no real .env file created
PASS: LICENSE is MIT
PASS: README has docker compose up quickstart and /health reference
PASS: git log --all -- .env returns nothing (secrets never in git history)
```

## Threat Model Coverage

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-01-01 | `.env` added to `.gitignore` before first code commit; `.env.example` has placeholders only | Mitigated |
| T-01-02 | `.gitattributes` with `* text=auto eol=lf` + `*.sh text eol=lf` | Mitigated |
| T-01-03 | Acceptance criteria verified: no `sk-ant-*` or real key patterns in `.env.example`; all values are `changeme-*` or `your-*-here` | Mitigated |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan creates only configuration and documentation files. No application code or data-flow stubs.

## Self-Check: PASSED

Files created:
- F:/My-home-lab/.gitignore — FOUND
- F:/My-home-lab/.gitattributes — FOUND
- F:/My-home-lab/.env.example — FOUND
- F:/My-home-lab/LICENSE — FOUND
- F:/My-home-lab/README.md — FOUND

Commits:
- 4553031 — FOUND (chore: .gitignore + .gitattributes)
- eaa2127 — FOUND (chore: .env.example)
- aea78e5 — FOUND (feat: LICENSE + README)
