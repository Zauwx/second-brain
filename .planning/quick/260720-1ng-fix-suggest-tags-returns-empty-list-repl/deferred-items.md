# Deferred Items — Quick Task 260720-1ng

## `ruff format --check` pre-existing failures (out of scope)

`uv run ruff format --check app/ tests/` reports 26 files would be reformatted
(e.g. `app/auth/models.py`, `app/collections/*`, `tests/test_auth.py`, etc.).

Confirmed via `git stash` that this predates this task's changes entirely —
it reproduces identically on the pre-Task-1 HEAD. Likely a Windows
line-ending / wrapping drift accumulated across prior phases, unrelated to
the `json_mode` -> `format=` seam rename this task performs.

Not fixed here per the executor's SCOPE BOUNDARY rule (only auto-fix issues
directly caused by the current task's changes). `uv run ruff check` (lint,
not format) passes clean with zero issues both before and after this task.

Files this task touched that also currently fail `ruff format --check`:
`app/ai/providers/ollama.py`, `tests/ai/test_live_ollama.py`,
`tests/ai/test_suggest_tags.py`, `tests/ai/test_summarize.py`,
`tests/conftest.py`. Verified via diff inspection (`ruff format --diff`) that
the specific hunks flagged are pre-existing formatting drift on lines this
task did not touch (e.g. an `@retry(...)` decorator line-wrap in
`ollama.py`), not newly introduced by this task's edits.

Recommend a dedicated quick task to run `ruff format` repo-wide in its own
commit, reviewed separately from behavior changes.
