---
phase: 4
slug: tags-collections-full-text-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-28
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode = auto) |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~60-120 seconds (testcontainers MySQL 8.4 spin-up + suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

> Task IDs are placeholders until the planner finalizes plan/wave structure. The planner MUST reconcile this map with the actual PLAN.md task IDs and fill the File Exists column.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-XX-XX | tags | 1 | ORG-01 | T-04-iso | Tag attach/detach scoped to owner; cross-user attach → 403/404 | integration | `uv run pytest tests/test_tags.py -q` | ❌ W0 | ⬜ pending |
| 04-XX-XX | tags | 2 | ORG-02 | — | `GET /notes?tag=python&tag=docker` returns AND-intersection, no N+1 | integration | `uv run pytest tests/test_notes_tag_filter.py -q` | ❌ W0 | ⬜ pending |
| 04-XX-XX | collections | 1 | ORG-03 | T-04-iso | Create collection + add note scoped to owner | integration | `uv run pytest tests/test_collections.py -q` | ❌ W0 | ⬜ pending |
| 04-XX-XX | collections | 1 | ORG-04 | — | `GET /collections/{id}/notes` returns the collection's notes (owner-scoped) | integration | `uv run pytest tests/test_collections.py -q` | ❌ W0 | ⬜ pending |
| 04-XX-XX | search | 1 | SRCH-01 | T-04-inj | `GET /search?q=docker` BOOLEAN MODE; 2-char "AI" returns; operator chars sanitized | integration | `uv run pytest tests/test_search.py -q` | ❌ W0 | ⬜ pending |
| 04-XX-XX | all | 1 | ORG-01..04 | T-04-iso | User A cannot read/modify user B's tags or collections | integration | `uv run pytest tests/test_phase4_isolation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — extend MySQL testcontainer with `--innodb-ft-min-token-size=2` so 2-char-token search (criterion 4) is reproducible; add tag/collection/user fixtures
- [ ] `tests/test_tags.py` — stubs for ORG-01 (create/attach/detach, per-user isolation)
- [ ] `tests/test_notes_tag_filter.py` — stubs for ORG-02 (single + multi-tag AND filter, N+1 assertion)
- [ ] `tests/test_collections.py` — stubs for ORG-03, ORG-04 (create, add/remove note, list notes)
- [ ] `tests/test_search.py` — stubs for SRCH-01 (BOOLEAN MODE match, 2-char token, operator sanitization)
- [ ] `tests/test_phase4_isolation.py` — stubs for cross-user isolation of tags + collections

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `SHOW VARIABLES LIKE 'innodb_ft_min_token_size'` returns 2 in the running container | SRCH-01 (criterion 4) | Verifies the live server startup variable, not just app behavior | `docker compose up`, then `docker compose exec mysql mysql -uroot -p$MYSQL_ROOT_PASSWORD -e "SHOW VARIABLES LIKE 'innodb_ft_min_token_size'"` → expect `2`. (Also asserted automatically in the search test via a real 2-char query.) |

*Note: the manual check above is belt-and-suspenders — the automated `tests/test_search.py` 2-char-token test is the binding proof.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
