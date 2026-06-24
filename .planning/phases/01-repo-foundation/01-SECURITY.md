---
phase: 1
slug: repo-foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-24
---

# Phase 1 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register authored at plan time (all three PLAN files carried a `<threat_model>` block).
All mitigations independently verified against the repository during this audit — see
the Evidence column. `threats_open: 0`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| working tree → git history (PUBLIC repo) | Once committed and pushed to the public `second-brain` repo, secrets are irreversibly world-readable in history | `.env` secrets (MySQL/JWT/Anthropic/Ollama credentials) |
| repo files → Linux container runtime | Windows-authored text crosses into a Linux container; CRLF breaks shell interpreters | Shell scripts, config files |
| env vars → application config | Untyped env input read into `Settings`; extra/unexpected vars must not crash the app | Configuration values |
| build context → Docker image layers | Files in the build context can be baked into shareable/pushable image layers | `.env`, local caches |
| host → container (runtime env) | Secrets must cross only at runtime via `env_file`, never via build args or `COPY` | Runtime secrets |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Information Disclosure | `.env` secrets reaching git history | mitigate | `.env` in `.gitignore` (line 10) before first commit; only `.env.example` placeholders committed; **verified:** `git log --all --full-history -- .env` returns nothing, `.env` not tracked | closed |
| T-01-02 | Tampering / Denial | CRLF line endings corrupting shell scripts in Linux containers | mitigate | `.gitattributes` `* text=auto eol=lf` (line 3) + explicit `*.sh`/`*.py eol=lf`; **verified present** | closed |
| T-01-03 | Information Disclosure | Real secret pasted into committed `.env.example` | mitigate | All values are placeholders; **verified:** no `sk-ant-*`/`AKIA`/PEM patterns, 7 placeholder tokens present | closed |
| T-01-04 | Denial of Service | `app.main:app` fails to start because `Settings` rejects rich `.env.example` vars for unbuilt phases | mitigate | `SettingsConfigDict(env_file=".env", extra="ignore")` in `app/core/config.py` (line 12); **verified present** | closed |
| T-01-05 | Information Disclosure | uv `.venv/` or caches committed, leaking local paths/state | mitigate | `.gitignore` excludes `.venv/` (28), `.pytest_cache/` (41), `.mypy_cache/` (48), `.ruff_cache/` (53); **verified present** | closed |
| T-01-06 | Information Disclosure | `.env` baked into Docker image layers | mitigate | `.dockerignore` excludes `.env` (line 12); Dockerfile COPYs only `pyproject.toml`/`uv.lock`/`app/` — no `COPY .env`, no secret `ENV`; compose `env_file` at runtime (line 20); **verified by Dockerfile read** | closed |
| T-01-07 | Information Disclosure | Real `.env` committed in first push to PUBLIC repo (irreversible) | mitigate | Same control as T-01-01; **verified post-push:** `git log --all --full-history -- .env` empty after push to `origin/master` | closed |
| T-01-08 | Spoofing / Elevation | Unauthenticated or wrong-account `gh` push creates repo under wrong identity | mitigate | Blocking `gh auth status` gate before `gh repo create`; **verified:** authenticated as `Zauwx` (active), repo owned by `Zauwx/second-brain` | closed |
| T-01-SC | Tampering (supply chain) | `uv` package installs during build/sync | accept | Pinned `uv.lock` (tracked) + `uv sync --frozen --no-dev` (Dockerfile line 26); only vetted high-reputation PyPI deps; no new packages introduced — see Accepted Risks Log | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01-SC | T-01-SC | Phase-1 dependencies (fastapi, uvicorn, pydantic-settings, ruff, mypy, pytest, httpx) are well-known, high-reputation PyPI packages vetted in STACK.md/CLAUDE.md. Reproducibility enforced via pinned `uv.lock` + `uv sync --frozen`; no `[ASSUMED]`/`[SUS]` packages introduced. Residual supply-chain risk accepted for a learning project at this phase; revisit with dependency scanning in Phase 7 (CI/CD hardening). | Zauwx | 2026-06-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-24 | 9 | 9 | 0 | /gsd:secure-phase (orchestrator-verified, short-circuit: plan-time register, all mitigations evidence-checked) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-24
