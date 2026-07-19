---
quick_id: 260719-snb
type: execute
mode: quick
autonomous: true
files_modified:
  - docker/Dockerfile

must_haves:
  truths:
    - "alembic.ini and alembic/ exist inside the api image at /app"
    - "`docker compose exec api alembic upgrade head` exits 0 against the running mysql service"
    - "POST /auth/register against localhost:8000 returns 201, not 500"
    - "No secrets are baked into the image (.env still excluded)"
    - "The ollama_data and mysql_data volumes are untouched"
  artifacts:
    - path: "docker/Dockerfile"
      provides: "COPY of alembic assets + venv on PATH"
      contains: "COPY alembic.ini"
  key_links:
    - from: "docker/Dockerfile"
      to: "/app/alembic/env.py"
      via: "COPY alembic/ ./alembic/"
      pattern: "COPY alembic/ \\./alembic/"
    - from: "docker compose exec api alembic"
      to: "/app/.venv/bin/alembic"
      via: "ENV PATH"
      pattern: "ENV PATH=\"/app/.venv/bin"
---

<objective>
Make Alembic migrations runnable inside the api container.

`docker/Dockerfile` copies only `pyproject.toml`, `uv.lock`, and `app/`. It never copies
`alembic.ini` or `alembic/`, so the command documented at `docker-compose.yml:16` —
`docker compose exec api alembic upgrade head` — cannot run. On a fresh MySQL volume the
schema is therefore never created and `POST /auth/register` returns HTTP 500 with
`(1146, "Table 'secondbrain.users' doesn't exist")`.

Purpose: close the gap found during the Phase 05 live verification checkpoint
(05-04-PLAN.md Task 3). The test suite never caught this because testcontainers runs
`alembic upgrade head` from the HOST working directory, where both assets exist.

Output: a corrected `docker/Dockerfile`, a rebuilt api image, and a migrated database.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@CLAUDE.md
@docker/Dockerfile
@docker-compose.yml
@.dockerignore

<findings>
<!-- Verified against the live container before planning. Do not re-derive. -->

1. TWO defects, not one. Adding the COPY lines alone is NOT sufficient.

   Defect A — missing assets. `docker compose exec api ls /app` currently shows only
   `.venv  app  pyproject.toml  uv.lock`.

   Defect B — alembic not on PATH. Verified in the running container:
       PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
       command -v alembic  ->  (not found)
       ls /app/.venv/bin/alembic  ->  /app/.venv/bin/alembic   (exists)
   `uv sync` installs into the project venv at `/app/.venv`. The CMD works because it uses
   `uv run`, which activates that venv. `docker compose exec` does not. So the command
   documented in docker-compose.yml would fail with "executable file not found" even after
   Defect A is fixed. Fix by putting the venv first on PATH — this makes the already-documented
   command work verbatim, with no docker-compose.yml change.

2. `alembic>=1.14.0,<2.0.0` is in `[project].dependencies` (NOT a dev group), so it survives
   `uv sync --frozen --no-dev`. No pyproject.toml change is needed.

3. `.dockerignore` does not exclude `alembic/` or `alembic.ini`. It DOES exclude `__pycache__/`
   (so the stale `alembic/__pycache__` and `alembic/versions/__pycache__` dirs on disk stay out
   of the image — correct) and `*.md` (irrelevant; `alembic/README` has no extension and
   `script.py.mako` is not markdown). No .dockerignore change is needed.

4. `alembic/env.py` imports `app.core.config`, `app.database`, `app.auth.models`, and
   `app.notes.models`, and reads the DSN from `settings.database_url` (an env var), overriding
   the placeholder in alembic.ini. `app/` is already copied and `.env` is already supplied at
   runtime via compose `env_file`, so no extra wiring is required.

5. `UserCreate` requires `email` (EmailStr) + `password` with policy: >= 8 chars, one uppercase,
   one lowercase, one digit, one symbol. `Passw0rd!` satisfies all five rules. Duplicate email
   returns 409, not 500 — so use a unique email when verifying.
</findings>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Copy alembic assets into the image and put the venv on PATH</name>
  <files>docker/Dockerfile</files>
  <action>
Edit `docker/Dockerfile` only. Make exactly two changes; change nothing else.

(a) After the `RUN uv sync --frozen --no-dev` line (currently line 26) and before
`COPY app/ ./app/`, add an `ENV` line placing the uv-managed virtualenv's bin directory
first on PATH: PATH set to `/app/.venv/bin:$PATH`. Comment it with the reason — `uv sync`
installs console scripts into `/app/.venv/bin`, and `docker compose exec` does not run
through `uv run`, so without this the `alembic` entry point is unreachable and the command
documented at docker-compose.yml:16 fails with "executable file not found". Note that the
existing CMD keeps using `uv run` and is unaffected.

(b) Alongside `COPY app/ ./app/`, add two COPY instructions bringing in `alembic.ini` and
the `alembic/` directory (as `./alembic/`). Place them AFTER the dependency-install layer so
the expensive `uv sync` layer is not invalidated when a migration is added. Comment them
explaining that alembic.ini + alembic/ (env.py, script.py.mako, versions/) are required for
`alembic upgrade head` to run inside the container, and that `alembic` itself ships in the
image because it is a main dependency, not a dev dependency.

Honor the security constraint stated at Dockerfile line 5: do NOT add `COPY .env`, do NOT add
any secret ENV line, and do NOT weaken `.dockerignore`. Do not modify pyproject.toml,
docker-compose.yml, .dockerignore, app/, tests/, or any file under alembic/versions/.

Do NOT add an entrypoint script, startup hook, or any automatic migration-on-boot behavior —
migrations remain a deliberate manual step (explicitly out of scope).
  </action>
  <verify>
    <automated>grep -v '^#' docker/Dockerfile | grep -c 'COPY alembic.ini' | grep -q '^1$' &amp;&amp; grep -v '^#' docker/Dockerfile | grep -q 'COPY alembic/ \./alembic/' &amp;&amp; grep -v '^#' docker/Dockerfile | grep -q 'ENV PATH="/app/.venv/bin' &amp;&amp; ! grep -v '^#' docker/Dockerfile | grep -q 'COPY .env'</automated>
  </verify>
  <done>docker/Dockerfile contains a COPY for alembic.ini, a COPY for alembic/, and an ENV PATH line prepending /app/.venv/bin. No COPY of .env or any secret ENV was introduced. No other file changed.</done>
</task>

<task type="auto">
  <name>Task 2: Rebuild the api service and prove migrations run end to end</name>
  <files>(no file changes — verification only)</files>
  <action>
Rebuild and restart ONLY the api service, then prove the fix end to end.

CRITICAL container-safety rules — a compose stack is already running (api, mysql, ollama), and
ollama holds a 2 GB llama3.2:3b download in the ollama_data volume:
  - NEVER run `docker compose down -v`, `docker volume rm`, `docker volume prune`, or
    `docker system prune`.
  - NEVER rebuild, restart, stop, or recreate the ollama service.
  - NEVER reset the mysql volume. The database must be migrated in place.
  - Scope every command to the api service by name.

Steps:
  1. `docker compose build api`
  2. `docker compose up -d api`  (recreates the api container only, leaving mysql and ollama running)
  3. Confirm the assets landed: `docker compose exec api ls /app` must list `alembic.ini` and
     `alembic`, in addition to the existing `.venv`, `app`, `pyproject.toml`, `uv.lock`.
  4. Confirm the entry point resolves: `docker compose exec api command -v alembic` must print
     `/app/.venv/bin/alembic`.
  5. Run the migration exactly as documented at docker-compose.yml:16:
     `docker compose exec api alembic upgrade head` — must exit 0.
  6. Confirm the schema exists: `docker compose exec api alembic current` should report a
     revision at head (the 0006 revision).
  7. Prove the original 500 is gone. POST to http://localhost:8000/auth/register with
     Content-Type: application/json and a body containing a UNIQUE email (append a timestamp,
     e.g. smoke+<epoch>@example.com) and password `Passw0rd!`. Expect HTTP 201.
     A 409 means that email already exists — retry with a fresh one. A 500 means the fix failed.

If the migration fails on an unexpected already-partially-migrated database, report the exact
error and stop. Do NOT resolve it by wiping the mysql volume.
  </action>
  <verify>
    <automated>docker compose exec -T api ls /app | grep -q '^alembic.ini$' &amp;&amp; docker compose exec -T api ls /app | grep -q '^alembic$' &amp;&amp; docker compose exec -T api command -v alembic &amp;&amp; docker compose exec -T api alembic upgrade head &amp;&amp; curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/auth/register -H 'Content-Type: application/json' -d "{\"email\":\"smoke+$(date +%s)@example.com\",\"password\":\"Passw0rd!\"}" | grep -q '^201$'</automated>
  </verify>
  <done>`docker compose exec api ls /app` lists alembic.ini and alembic/; `alembic` resolves to /app/.venv/bin/alembic; `alembic upgrade head` exits 0; POST /auth/register returns 201. The ollama and mysql containers were never rebuilt or recreated, and no volume was removed.</done>
</task>

</tasks>

<verification>
- `docker/Dockerfile` copies alembic.ini and alembic/ and prepends /app/.venv/bin to PATH.
- No `COPY .env` and no secret ENV line exists in the Dockerfile; `.dockerignore` is unchanged.
- The migration command documented at docker-compose.yml:16 runs successfully verbatim, with no
  docker-compose.yml edit required.
- `POST /auth/register` returns 201 instead of the 500 / "Table 'secondbrain.users' doesn't exist".
- `docker compose ps` still shows ollama and mysql with their original container IDs / uptime
  (only api was recreated), and `docker volume ls` still lists ollama_data and mysql_data.
- No changes under app/, tests/, alembic/versions/, or ROADMAP.md.
</verification>

<success_criteria>
Migrations can be run inside the api container using the already-documented command, the
schema is created against the existing mysql volume, user registration succeeds with 201, and
the 2 GB ollama model download is preserved.
</success_criteria>

<output>
Create `.planning/quick/260719-snb-fix-copy-alembic-ini-alembic-into-api-im/260719-snb-SUMMARY.md` when done.
</output>
