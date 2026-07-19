---
phase: 5
slug: local-ai-ollama
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-05
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ai -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~60-120 seconds (testcontainers MySQL spin-up dominates) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ai -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | AIL-01 | — | Ollama service reachable only on internal Docker network (not host-exposed) | integration | `uv run pytest tests/ai -q` | ❌ W0 | ⬜ pending |

*Populated by the planner/executor from PLAN.md task IDs. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/ai/` package — test module(s) for the AI endpoints (summarize, suggest-tags, health/degradation)
- [ ] `tests/conftest.py` — `FakeLLMProvider` fixture + `app.dependency_overrides[get_llm_provider]` wiring (mirrors existing `get_db` override); zero real Ollama calls
- [ ] Existing testcontainers MySQL harness + per-user 404/403 ownership fixtures cover the note-resolution path

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose up` starts api+mysql+ollama; `GET /health` confirms ollama reachable | AIL-01 | Requires live Docker + pulled model, not run in CI test suite | `docker compose up -d && docker compose exec ollama ollama pull llama3.2:3b`; then `curl localhost:8000/health` shows ollama reachable |
| Ollama container stays within configured memory limit during summarization (OOM guard) | AIL-01 | Requires `docker stats` observation against live inference | Trigger `POST /ai/summarize`, observe `docker stats` mem usage stays under the `mem_limit: 4g` cap |
| Real summary quality (2-3 sentences) + real tag JSON from llama3.2:3b | AIL-01, AIL-02 | LLM output is non-deterministic; unit tests mock the provider | Manually call both endpoints via Swagger against the live Ollama service |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
