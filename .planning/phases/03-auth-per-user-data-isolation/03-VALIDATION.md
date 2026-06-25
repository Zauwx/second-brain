---
phase: 03
slug: auth-per-user-data-isolation
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-25
last_audited: 2026-06-25
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 0.24.x (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (already configured) |
| **Quick run command** | `uv run pytest tests/test_auth.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~30s quick / ~60-90s full (testcontainers MySQL spin-up dominates) |

*Requires Docker Desktop running for testcontainers mysql:8.4.*

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | AUTH-01/02 | T-03-06 / T-03-SC | Block install of unverified auth packages until human-verified | checkpoint | n/a (blocking-human gate) | n/a | ✅ manual-done |
| 03-01-02 | 01 | 1 | AUTH-01/02 | T-03-04 | JWT settings load from .env; secret never hard-coded | integration | `uv run python -c "from app.core.config import settings; import jwt, pwdlib"` | ✔ | ✅ green |
| 03-01-03 | 01 | 1 | AUTH-01 | T-03-01/03 | register 201; dup 409; bad email/weak pw 422; hash never returned | integration | `uv run pytest tests/test_auth.py -x -k register` | ✔ | ✅ green (7) |
| 03-01-03 | 01 | 1 | AUTH-02 | T-03-02/05 | login 200 token pair; wrong pw/unknown email 401; access token signed | integration | `uv run pytest tests/test_auth.py -x -k login` | ✔ | ✅ green (3) |
| 03-02-01 | 02 | 2 | AUTH-03 | T-03-08/09/12/13 | get_current_user 401 on missing/expired/invalid/deleted-user | integration | `uv run pytest tests/test_auth.py -x -k "token or current_user"` | ✔ | ✅ green |
| 03-02-02 | 02 | 2 | AUTH-03 | T-03-10/11/14 | refresh rotates + revokes old jti; logout 204; refresh-after-logout 401; siblings independent | integration | `uv run pytest tests/test_auth.py -x -k "refresh or logout"` | ✔ | ✅ green |
| 03-03-01 | 03 | 3 | AUTH-04 | T-03-17/20 | notes.user_id NOT NULL FK; NoteCreate omits user_id | integration | `uv run python -c "from app.notes.models import Note; from app.notes.schemas import NoteCreate, NoteRead"` + migration via conftest | ✔ | ✅ green |
| 03-03-02 | 03 | 3 | AUTH-04 | T-03-15/16/19 | repo scopes create+list to user_id; service 403/404 ownership | unit | `uv run pytest tests/test_notes_service_isolation.py -x` + `uv run mypy app/notes/` | ✔ | ✅ green (6) |
| 03-03-03 | 03 | 3 | AUTH-04 | T-03-15/16/17/18/19 | no-token 401; cross-user 403; missing 404; list isolation; owner assigned server-side | integration | `uv run pytest tests/test_notes_isolation.py -x` then `uv run pytest tests/ -x` | ✔ | ✅ green (9) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_auth.py` — register/login (Plan 01 Task 3), refresh/logout/401 (Plan 02) — covers AUTH-01, AUTH-02, AUTH-03 — **28 tests green**
- [x] `tests/test_notes_isolation.py` — cross-user 403/404, list isolation, owner assignment, no-token 401 (Plan 03 Task 3) — covers AUTH-04 — **9 tests green**
- [x] `tests/conftest.py` additions — `registered_user`, `auth_client` (Plan 01); `user_a_client`, `user_b_client` (Plan 03)
- [x] Existing `tests/test_notes_crud.py` + `tests/test_notes_list.py` — swap `client` → `auth_client` fixture (Plan 03 Task 3, Pitfall 5) — **28 tests green**

*Framework already installed (pytest + pytest-asyncio + testcontainers). No framework install needed — only new test files + fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Package legitimacy of pyjwt / pwdlib / email-validator | AUTH-01/02 | slopcheck unavailable; [ASSUMED-OK] packages require human PyPI verification before install (package legitimacy gate) | Plan 01 Task 1 blocking-human checkpoint — confirm the three PyPI pages match expected repos/authors |
| Full lifecycle via Swagger (register → login → Authorize → /notes → refresh → logout → refresh fails 401) | AUTH-01..04 | End-to-end UX confidence beyond automated tests | Optional: run `docker compose up`, exercise the flow in /docs (all assertions are also covered by automated tests) |

*All phase behaviors have automated verification; the Swagger walkthrough is an optional confidence check, not a gate.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Task 03-01-01 is the legitimacy checkpoint by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_auth.py, test_notes_isolation.py, conftest fixtures)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-25

---

## Validation Audit 2026-06-25

Retroactive audit of the executed phase (State A — VALIDATION.md existed from plan time with all rows ⬜ pending). Verified the projected Wave 0 test deliverables exist and run green.

| Metric | Count |
|--------|-------|
| Requirements audited | 4 (AUTH-01..04) |
| Per-task rows | 9 |
| Gaps found | 0 |
| Resolved (now green) | 8 automated + 1 manual-by-design |
| Escalated | 0 |

**Evidence:** `uv run pytest tests/ -q` → **72 passed in 14.41s** (Docker Desktop up, testcontainers mysql:8.4). Every requirement slice resolves to real tests:
- AUTH-01 register → 7 tests · AUTH-02 login → 3 tests
- AUTH-03 current_user/refresh/logout → `test_auth.py` (28 total)
- AUTH-04 isolation → `test_notes_isolation.py` (9) + `test_notes_service_isolation.py` (6)

**Verdict:** NYQUIST-COMPLIANT. No gaps to fill; auditor not spawned.
