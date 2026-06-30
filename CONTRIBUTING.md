# Contributing to Second Brain

Thanks for your interest in contributing! Second Brain is a self-hosted personal
knowledge base built primarily as a learning project, and contributions —
bug reports, fixes, docs, and features — are genuinely welcome.

This document explains how to get set up, the conventions we follow, and what a
good pull request looks like.

By participating, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Table of Contents

- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Project layout](#project-layout)
- [Quality gates (run these before pushing)](#quality-gates-run-these-before-pushing)
- [Branching & commit conventions](#branching--commit-conventions)
- [Pull request process](#pull-request-process)
- [Reporting bugs & requesting features](#reporting-bugs--requesting-features)
- [Security issues](#security-issues)

---

## Ways to contribute

- **Report a bug** — open an issue using the *Bug report* template.
- **Request a feature** — open an issue using the *Feature request* template so it
  can be discussed before code is written.
- **Improve docs** — typos, clarifications, and examples are always appreciated.
- **Submit code** — fix a bug or implement an agreed-upon feature via a pull request.

For anything non-trivial, please open an issue first so we can align on the
approach before you invest time in a PR.

---

## Development setup

Prerequisites:

- [uv](https://docs.astral.sh/uv/) (package & environment manager)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker +
  Docker Compose) — required to run the app and the test suite (tests use a real
  MySQL 8.4 container via testcontainers)
- Python 3.12 (uv will fetch it if you don't have it)

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/second-brain.git
cd second-brain

# 2. Install dependencies (creates the virtualenv and installs dev tools)
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env: set MYSQL_* credentials, a matching DATABASE_URL, and a JWT_SECRET_KEY
#   python -c "import secrets; print(secrets.token_hex(32))"

# 4. Start the stack
docker compose up -d --build

# 5. Apply migrations
docker compose exec api alembic upgrade head

# 6. Open the API docs
#   http://localhost:8000/docs
```

---

## Project layout

The app follows a **domain-per-folder** layout under `app/`. Each domain uses the
same layered structure:

```
router  (HTTP)  →  service  (business logic)  →  repository  (data access)  →  model / schemas
```

When adding a feature, keep it inside its domain folder and respect these layers —
routers stay thin, business rules live in services, and all DB access goes through
repositories. Every query that returns user data **must** be scoped to the
authenticated user (see existing `get_or_404_owned` usage). Multi-user data
isolation is a hard requirement, not an optional nicety.

---

## Quality gates (run these before pushing)

All three must pass locally. CI will enforce them too.

```bash
# Lint & format
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/

# Static type checking
uv run mypy app/

# Tests (requires Docker running — spins up a MySQL 8.4 testcontainer)
uv run pytest
```

Guidelines:

- **New behavior needs tests.** We follow a test-first style: add a failing test
  that captures the desired behavior, then make it pass.
- Keep the full suite green. Don't disable or `xfail` tests to get a PR through.
- New code must be fully type-annotated (`mypy` runs without errors).

---

## Branching & commit conventions

- Branch off `master`. Use a descriptive name, e.g. `fix/tag-filter-empty-query`
  or `feat/export-notes-markdown`.
- We use **[Conventional Commits](https://www.conventionalcommits.org/)**:

  ```
  <type>(<optional scope>): <short summary>
  ```

  Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `style`,
  `perf`, `ci`. Examples:

  ```
  feat(search): support phrase queries in BOOLEAN MODE
  fix(notes): scope tag filter to the authenticated user
  docs: clarify .env setup for Docker
  ```

- Keep commits focused and atomic — one logical change per commit.

---

## Pull request process

1. Ensure your branch is up to date with `master` and the quality gates pass.
2. Open a PR against `master` and fill in the PR template.
3. Link any related issue (`Closes #123`).
4. Describe **what** changed and **why**, and how you verified it.
5. Be responsive to review feedback — small follow-up commits are fine; we squash
   on merge where appropriate.

A PR is ready to merge when:

- [ ] `ruff`, `mypy`, and `pytest` all pass
- [ ] New behavior is covered by tests
- [ ] User-facing changes are reflected in the README/docs
- [ ] The change preserves per-user data isolation

---

## Reporting bugs & requesting features

Please use the issue templates (Bug report / Feature request). Good bug reports
include: what you did, what you expected, what actually happened, and the minimal
steps to reproduce (plus relevant logs and your environment).

## Security issues

**Do not** open a public issue for security vulnerabilities. See
[SECURITY.md](SECURITY.md) for how to report them privately.

---

Thanks again for contributing! 💜
