---
quick_id: 260719-snb
type: execute
mode: quick
subsystem: infra
tags: [docker, alembic, dockerfile, migrations]

# Dependency graph
requires:
  - phase: 05-local-ai-ollama
    provides: "Live verification checkpoint (05-04 Task 3) that surfaced the missing-alembic-assets bug"
provides:
  - "api image with alembic.ini + alembic/ copied in, and /app/.venv/bin on PATH"
  - "Working `docker compose exec api alembic upgrade head` exactly as documented in docker-compose.yml"
affects: [05-04, deployment, future-migrations]

tech-stack:
  added: []
  patterns:
    - "Docker layer ordering: COPY alembic assets after `uv sync` (cheap layer, doesn't invalidate the expensive dependency-install cache) but the layer itself stays static unless migrations change"
    - "ENV PATH=\"/app/.venv/bin:$PATH\" pattern for making uv-installed console scripts reachable via `docker compose exec`, independent of the CMD's `uv run` wrapper"

key-files:
  created: []
  modified:
    - docker/Dockerfile

key-decisions:
  - "Fixed via ENV PATH prepend rather than changing CMD or the documented docker-compose.yml command — makes the already-documented `docker compose exec api alembic upgrade head` work verbatim, no other file needed changes"

patterns-established:
  - "Alembic assets (alembic.ini, alembic/) must be copied into any image where migrations are expected to run via `docker compose exec`, in addition to app/ source"

requirements-completed: []

duration: 15min
completed: 2026-07-19
---

# Quick Task 260719-snb: Fix missing alembic assets in api Docker image

**Copied `alembic.ini` + `alembic/` into the api image and prepended `/app/.venv/bin` to PATH, fixing `docker compose exec api alembic upgrade head` and the resulting 500 on `POST /auth/register` against a fresh MySQL volume.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 completed
- **Files modified:** 1 (`docker/Dockerfile`)

## Accomplishments

- `docker/Dockerfile` now copies `alembic.ini` and `alembic/` into the image, and puts the uv-managed venv's `bin/` directory first on `PATH`.
- Rebuilt only the `api` service (`docker compose build api` + `docker compose up -d api`); `mysql` and `ollama` were never touched (confirmed via unchanged uptime and `docker volume ls`).
- `docker compose exec api alembic upgrade head` now runs successfully end-to-end against the live `mysql` service, applying all six migrations (`d51191e92276` → `0006_add_note_summary`) to a database that previously had no schema.
- `docker compose exec api alembic current` reports `0006_add_note_summary (head)`.
- `POST /auth/register` against `localhost:8000` now returns `201` (previously `500` — `Table 'secondbrain.users' doesn't exist`).

## Task Commits

1. **Task 1: Copy alembic assets into the image and put the venv on PATH** — `29d4b73` (fix)
2. **Task 2: Rebuild the api service and prove migrations run end to end** — no commit (verification-only task, no file changes)

**Plan metadata:** committed separately by the orchestrator (docs artifacts excluded from executor commits per task instructions).

## Files Created/Modified

- `docker/Dockerfile` — added `ENV PATH="/app/.venv/bin:$PATH"` after `RUN uv sync --frozen --no-dev`, and added `COPY alembic.ini ./alembic.ini` + `COPY alembic/ ./alembic/` after `COPY app/ ./app/`.

## Decisions Made

- Used an `ENV PATH` prepend (rather than modifying `docker-compose.yml`'s documented command, or switching the CMD to `uv run alembic ...`) so the already-documented `docker compose exec api alembic upgrade head` works verbatim with zero changes outside `docker/Dockerfile`.

## Deviations from Plan

None — plan executed exactly as written. Both defects identified in the plan's `<findings>` (missing assets, alembic not on PATH) were fixed with the two changes specified in Task 1; no additional issues were discovered during Task 2's verification.

One minor environment-only note (not a deviation from the plan, no file changes involved): the plan's verification command `docker compose exec -T api command -v alembic` fails under `docker compose exec` because `command` is a shell builtin and `exec` does not invoke a shell by default (`OCI runtime exec failed: exec: "command": executable file not found in $PATH`). This is a property of how `docker compose exec` invokes processes, not a defect in the fix. Verified the equivalent behavior instead via:
- `docker compose exec -T api sh -c "command -v alembic"` → `/app/.venv/bin/alembic`
- The direct functional test `docker compose exec -T api alembic upgrade head` → exit 0, applying all 6 migrations

Both confirm the alembic entry point resolves correctly and is fully usable via `docker compose exec`.

## Issues Encountered

None blocking. See the shell-builtin note above under Deviations — worked around during verification, no code or Dockerfile change required.

## User Setup Required

None — no external service configuration required. The fix is entirely internal to the `docker/Dockerfile`.

## Verification Evidence

```
$ docker compose build api
... (uses cached layers through uv sync, only re-runs COPY app/, COPY alembic.ini, COPY alembic/) ...
Image my-home-lab-api Built

$ docker compose up -d api
Container my-home-lab-ollama-1 Running   (untouched)
Container my-home-lab-mysql-1  Running   (untouched)
Container my-home-lab-api-1    Recreated

$ docker compose exec -T api ls -a /app
.  ..  .venv  alembic  alembic.ini  app  pyproject.toml  uv.lock

$ docker compose exec -T api sh -c "command -v alembic"
/app/.venv/bin/alembic

$ docker compose exec -T api alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> d51191e92276, create notes table
INFO  [alembic.runtime.migration] Running upgrade d51191e92276 -> a1b2c3d4e5f6, create users and refresh_tokens tables
INFO  [alembic.runtime.migration] Running upgrade a1b2c3d4e5f6 -> 0003_add_user_id_to_notes, add user_id FK to notes table
INFO  [alembic.runtime.migration] Running upgrade 0003_add_user_id_to_notes -> 0004_add_tags, ...
INFO  [alembic.runtime.migration] Running upgrade 0004_add_tags -> 0005_add_collections, ...
INFO  [alembic.runtime.migration] Running upgrade 0005_add_collections -> 0006_add_note_summary, ...
(exit code 0)

$ docker compose exec -T api alembic current
0006_add_note_summary (head)

$ curl -s -w '\nHTTP_STATUS:%{http_code}\n' -X POST http://localhost:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke+1784486581@example.com","password":"Passw0rd!"}'
{"id":1,"email":"smoke+1784486581@example.com","created_at":"2026-07-19T18:43:01"}
HTTP_STATUS:201

$ docker compose ps
my-home-lab-api-1     ... Up About a minute      (recreated, expected)
my-home-lab-mysql-1   ... Up 46 minutes (healthy) (untouched)
my-home-lab-ollama-1  ... Up 46 minutes (healthy) (untouched)

$ docker volume ls | grep -E "ollama_data|mysql_data"
local     my-home-lab_mysql_data
local     my-home-lab_ollama_data
```

## Next Phase Readiness

- The gap found during the Phase 05 live verification checkpoint (05-04 Task 3) is now closed: migrations can be run inside the `api` container using the documented `docker compose exec api alembic upgrade head` command, and user registration works against a freshly migrated database.
- 05-04's live end-to-end checkpoint (Task 3) can now proceed/be re-attempted without hitting the `Table 'secondbrain.users' doesn't exist` 500 error.
- No new blockers introduced.

---
*Quick task: 260719-snb*
*Completed: 2026-07-19*

## Self-Check: PASSED

- FOUND: docker/Dockerfile
- FOUND: commit 29d4b73 (Task 1)
- FOUND: 260719-snb-SUMMARY.md
