---
phase: "01-repo-foundation"
plan: "02"
subsystem: "fastapi-skeleton"
tags: [fastapi, uv, ruff, mypy, pydantic-settings, health-endpoint, domain-layout, pytest, httpx]

dependency_graph:
  requires:
    - "01-01: .gitignore excludes .venv/, .ruff_cache/, .mypy_cache/, .pytest_cache/ (T-01-05 mitigation)"
  provides:
    - "pyproject.toml: uv-managed project with fastapi 0.115.x, uvicorn 0.32.x, pydantic-settings 2.x"
    - "app/core/config.py: Settings(BaseSettings) with extra=ignore — accepts future-phase env vars"
    - "app/api/health.py: GET /health -> 200 {'status': 'ok'}"
    - "app/main.py: FastAPI app 'Second Brain' with health router registered"
    - "domain-per-folder placeholders: app/notes, app/services, app/repositories (empty __init__.py)"
    - "tests/test_health.py: passing httpx/ASGITransport health test (no live server)"
    - "uv.lock: committed reproducible lockfile"
    - ".python-version: pins to Python 3.12"
  affects:
    - "Plan 03 (Docker): app.main:app is the entry point for uvicorn in Dockerfile"
    - "Phase 2 (Database): app/notes, app/services, app/repositories placeholders ready for CRUD"
    - "ROADMAP criterion 4: uv run ruff check app/ passes clean"

tech_stack:
  added:
    - "fastapi 0.115.14 (runtime)"
    - "uvicorn[standard] 0.32.1 (runtime ASGI server)"
    - "pydantic-settings 2.14.2 (settings management)"
    - "ruff 0.15.19 (lint+format, dev)"
    - "mypy 2.1.0 (static typing, dev)"
    - "pytest 9.1.1 + pytest-asyncio 1.4.0 (testing, dev)"
    - "httpx 0.28.1 (test client, dev)"
    - "uv 0.11.24 (package manager)"
  patterns:
    - "pydantic BaseSettings with extra=ignore (12-factor config, future-proof)"
    - "APIRouter pattern (router has zero business logic)"
    - "httpx.AsyncClient + ASGITransport for in-process async testing"
    - "asyncio_mode=auto in pyproject.toml (no per-test decorator)"
    - "domain-per-folder layout (app/core, app/api, app/notes, app/services, app/repositories)"

key_files:
  created:
    - path: "pyproject.toml"
      role: "uv project metadata, runtime deps, dev deps, ruff/mypy/pytest config"
    - path: "uv.lock"
      role: "Committed reproducible lockfile (not gitignored per convention)"
    - path: ".python-version"
      role: "Pins uv to CPython 3.12.x (avoids 3.14 default download)"
    - path: "app/__init__.py"
      role: "Top-level app package init"
    - path: "app/main.py"
      role: "FastAPI app factory — includes health router, expose app at module level"
    - path: "app/core/__init__.py"
      role: "core package init"
    - path: "app/core/config.py"
      role: "Settings(BaseSettings) with extra=ignore; module-level settings instance"
    - path: "app/api/__init__.py"
      role: "api package init"
    - path: "app/api/health.py"
      role: "APIRouter — GET /health returning 200 {status: ok}"
    - path: "app/notes/__init__.py"
      role: "Empty domain placeholder for Phase 2 notes CRUD"
    - path: "app/services/__init__.py"
      role: "Empty domain placeholder for Phase 2 business logic layer"
    - path: "app/repositories/__init__.py"
      role: "Empty domain placeholder for Phase 2 data access layer"
    - path: "tests/__init__.py"
      role: "tests package init"
    - path: "tests/test_health.py"
      role: "Async httpx test: asserts GET /health returns 200 and {status: ok}"
  modified: []

decisions:
  - "Pinned Python 3.12 via .python-version file — uv defaulted to 3.14 when no version was specified; 3.12 is required by CLAUDE.md (3.13+ drops crypt module, breaks passlib alternatives)"
  - "Used [dependency-groups] instead of deprecated [tool.uv.dev-dependencies] — uv 0.11.24 warns about the old field and recommends the PEP 735 standard"
  - "Settings.extra=ignore (T-01-04 mitigation) — rich .env.example with MySQL/JWT/Anthropic/Ollama vars does not crash Phase-1 startup"
  - "Health router has no prefix — GET /health not GET /api/health; simplest contract, matches README quickstart"

metrics:
  duration_minutes: 12
  completed_date: "2026-06-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 14
  files_modified: 0
---

# Phase 01 Plan 02: FastAPI Skeleton — Summary

uv-managed Python 3.12 project with FastAPI skeleton: pydantic-settings config, GET /health endpoint, domain-per-folder placeholders for Phase 2, ruff-clean code, and a passing httpx/ASGITransport test — all containerization-ready for Plan 03.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Initialize uv project with ruff + mypy config and FastAPI deps | fef33e5 | `pyproject.toml`, `uv.lock`, `.python-version` |
| 2 | Build the FastAPI skeleton — config, health router, app assembly, domain placeholders | d670035 | `app/__init__.py`, `app/main.py`, `app/core/__init__.py`, `app/core/config.py`, `app/api/__init__.py`, `app/api/health.py`, `app/notes/__init__.py`, `app/services/__init__.py`, `app/repositories/__init__.py` |
| 3 | Add the health endpoint test (local app-level smoke test via httpx) | 43d22fd | `tests/__init__.py`, `tests/test_health.py` |

## What Was Built

**Task 1 — pyproject.toml and uv project:**
- `pyproject.toml` with `requires-python = ">=3.12"`, runtime deps: `fastapi>=0.115.0,<0.116.0`, `uvicorn[standard]>=0.32.0,<0.33.0`, `pydantic-settings>=2.0.0,<3.0.0`.
- Dev deps in `[dependency-groups]`: ruff >=0.8.0, mypy >=1.13.0, pytest >=8.0.0, pytest-asyncio >=0.24.0, httpx >=0.28.0.
- `[tool.ruff]`: target py312, E/W/F/I/B/C4/UP/N/SIM rule sets, line-length 100.
- `[tool.mypy]`: python_version="3.12", strict type checking (disallow_untyped_defs, etc.).
- `[tool.pytest.ini_options]`: asyncio_mode="auto", testpaths=["tests"].
- `.python-version` file pins uv to CPython 3.12.13.
- `uv.lock` committed for reproducible installs.

**Task 2 — FastAPI skeleton:**
- `app/core/config.py`: `Settings(BaseSettings)` with `SettingsConfigDict(env_file=".env", extra="ignore")`. Phase 1 only needs `environment` and `log_level` with defaults — extra future-phase vars are ignored silently. Module-level `settings = Settings()` instance for dependency injection.
- `app/api/health.py`: `APIRouter` with `GET /health` returning `{"status": "ok"}` with async function and typed return `dict[str, str]`.
- `app/main.py`: `FastAPI(title="Second Brain")` app with `app.include_router(health_router)`. Module-level `app` object for `uvicorn app.main:app`.
- Empty `__init__.py` placeholder files for all six app packages, including the three domain folders (`notes`, `services`, `repositories`) that Phase 2 will populate.

**Task 3 — Health endpoint test:**
- `tests/test_health.py`: single `async def test_health_returns_200_and_ok_body()` function using `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. Asserts `response.status_code == 200` and `response.json() == {"status": "ok"}`. No live server, no external process.
- `asyncio_mode="auto"` from pyproject.toml — no `@pytest.mark.asyncio` decorator needed (though one was added for clarity and to satisfy mypy).

## Verification Results

All plan verification commands pass:

```
PASS: uv sync exits 0, 34 packages installed on Python 3.12.13
PASS: uv run python -c "import fastapi, uvicorn, pydantic_settings; print('deps ok')" -> deps ok
PASS: uv run ruff check app/ -> All checks passed!
PASS: from app.main import app; '/health' in [r.path for r in app.routes]
PASS: uv run pytest tests/test_health.py -q -> 1 passed in 0.21s
PASS: grep -Eiq 'passlib|python-jose|aiomysql' pyproject.toml -> no forbidden libs
PASS: pyproject.toml contains [tool.ruff], [tool.mypy], asyncio_mode = "auto"
```

## Threat Model Coverage

| Threat ID | Mitigation | Status |
|-----------|-----------|--------|
| T-01-04 | `SettingsConfigDict(extra="ignore")` in app/core/config.py — future-phase env vars do not crash Phase-1 startup | Mitigated |
| T-01-05 | .gitignore from Plan 01 excludes .venv/, .ruff_cache/, .mypy_cache/, .pytest_cache/ — verified present in depends_on 01-01 | Mitigated (inherited) |
| T-01-SC | All Phase-1 deps (fastapi, uvicorn, pydantic-settings, ruff, mypy, pytest, httpx) are well-known PyPI packages vetted in STACK.md/CLAUDE.md | Accepted |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pinned Python 3.12 via .python-version**
- **Found during:** Task 1
- **Issue:** uv defaulted to downloading and using Python 3.14.6 when no version was pinned. The plan requires Python 3.12 (CLAUDE.md: "Pin to 3.12 in Dockerfiles"; 3.13+ breaks passlib alternatives).
- **Fix:** Created `.python-version` file with `3.12`, ran `uv python install 3.12`, recreated `.venv`. uv now uses CPython 3.12.13.
- **Files modified:** `.python-version` (new file)
- **Commit:** fef33e5

**2. [Rule 1 - Deprecation] Replaced [tool.uv.dev-dependencies] with [dependency-groups]**
- **Found during:** Task 1
- **Issue:** uv 0.11.24 warned that `[tool.uv.dev-dependencies]` is deprecated and will be removed in a future release.
- **Fix:** Replaced with standard `[dependency-groups]` table (PEP 735), which uv 0.11.24 supports natively.
- **Files modified:** `pyproject.toml`
- **Commit:** fef33e5

## Known Stubs

None — all code is wired and functional. The domain placeholder files (`app/notes/__init__.py`, `app/services/__init__.py`, `app/repositories/__init__.py`) are intentionally empty scaffolding (not stubs) to be populated in Phase 2.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings beyond what the plan specifies.

## Self-Check: PASSED

Files created:
- F:/My-home-lab/pyproject.toml — FOUND
- F:/My-home-lab/uv.lock — FOUND
- F:/My-home-lab/.python-version — FOUND
- F:/My-home-lab/app/__init__.py — FOUND
- F:/My-home-lab/app/main.py — FOUND
- F:/My-home-lab/app/core/__init__.py — FOUND
- F:/My-home-lab/app/core/config.py — FOUND
- F:/My-home-lab/app/api/__init__.py — FOUND
- F:/My-home-lab/app/api/health.py — FOUND
- F:/My-home-lab/app/notes/__init__.py — FOUND
- F:/My-home-lab/app/services/__init__.py — FOUND
- F:/My-home-lab/app/repositories/__init__.py — FOUND
- F:/My-home-lab/tests/__init__.py — FOUND
- F:/My-home-lab/tests/test_health.py — FOUND

Commits:
- fef33e5 — chore(01-02): initialize uv project
- d670035 — feat(01-02): add FastAPI skeleton
- 43d22fd — test(01-02): add httpx/ASGITransport health endpoint test
