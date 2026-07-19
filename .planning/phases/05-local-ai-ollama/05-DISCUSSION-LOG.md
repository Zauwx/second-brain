# Phase 5: Local AI (Ollama) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-05
**Phase:** 5-Local AI (Ollama)
**Areas discussed:** Summarize behavior, Suggested tags flow, Provider abstraction, Failure/degradation

---

## Summarize behavior — response mode

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous (wait) | Client calls, request blocks until summary ready (~5-30s), summary returned in response. Simplest to build/demo in Swagger; fine for single-user tool. | ✓ |
| Background job | Return 202, run inference in BackgroundTask, persist, client re-fetches. More moving parts. | |

**User's choice:** Synchronous (wait)
**Notes:** Criterion 2 permits either; sync chosen for simplicity at personal single-user scale. Set a generous timeout (D-01).

---

## Summarize behavior — summary persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Persist on the note | Add nullable `Note.summary` column (new Alembic migration); summarize writes it, GET /notes returns it. | ✓ |
| Ephemeral (return only) | Generate + return but don't store. Simpler, no schema change. | |

**User's choice:** Persist on the note
**Notes:** More useful; exercises another migration (D-02).

---

## Suggested tags flow

| Option | Description | Selected |
|--------|-------------|----------|
| Suggest only (return list) | Return JSON list of proposed tags; user attaches chosen ones via existing Phase-4 endpoint. Human-in-the-loop. | ✓ |
| Auto-attach | Immediately create+attach via Phase-4 find-or-create. One-click but LLM writes directly to the note. | |

**User's choice:** Suggest only (return list)
**Notes:** Matches the "suggest" naming; keeps a human in the loop (D-04).

---

## Provider abstraction

| Option | Description | Selected |
|--------|-------------|----------|
| Thin abstraction now | LLMProvider protocol + OllamaProvider impl now; Phase 6 slots in AnthropicProvider. | ✓ |
| Minimal Ollama client | Concrete Ollama client only; introduce abstraction in Phase 6. | |

**User's choice:** Thin abstraction now
**Notes:** In-scope per phase goal ("LLM provider abstraction"); keep it minimal, one Protocol + one impl (D-06).

---

## Failure/degradation — Ollama unavailable

| Option | Description | Selected |
|--------|-------------|----------|
| 503 Service Unavailable | Clear message; core note app keeps working without AI. | ✓ |
| 500 Internal Error | Generic; conflates 'AI off' with 'app broke'. | |

**User's choice:** 503 Service Unavailable
**Notes:** AI is an optional enhancement layer (D-07).

---

## Failure/degradation — retries

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, bounded retry | tenacity: a couple of retries + short backoff for transient/cold-start timeouts, then 503. | ✓ |
| No retry | One attempt; fail fast. | |

**User's choice:** Yes, bounded retry
**Notes:** CLAUDE.md already prescribes tenacity for Ollama timeouts (D-08).

---

## Failure/degradation — memory limit

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit limit (~4GB) | Memory limit on ollama service in docker-compose; satisfies criterion 4, verifiable via docker stats. | ✓ |
| No limit | Simpler but fails criterion 4; risks OOM-killing other containers. | |

**User's choice:** Explicit limit (~4GB)
**Notes:** llama3.2:3b ~2GB + overhead; planner tunes exact value (D-09).

---

## Model choice

| Option | Description | Selected |
|--------|-------------|----------|
| One model (llama3.2:3b) | Use for both summary + tags (prompt for JSON list). One model to pull/prebake, less memory. | ✓ |
| Add qwen2.5:3b for tags | Specialized structured-JSON tagging model; better output, two models, more memory. | |

**User's choice:** One model (llama3.2:3b)
**Notes:** Criterion 2 names llama3.2:3b; planner handles lenient JSON parsing of tag output (D-05).

---

## Claude's Discretion

- Exact endpoint URL shape (`/ai/summarize` + `/ai/suggest-tags` vs `/notes/{id}/...`).
- Prompt wording for summarize + tag-suggest; strictness of tag JSON parsing.
- Ollama client/call style (`AsyncClient`) and host discovery on the Docker network.
- Model provisioning (runtime pull vs prebaked) and the `/health` Ollama probe.
- Exact tenacity retry count/backoff and the synchronous request timeout value.
- `mem_limit` vs `deploy.resources.limits` for the ollama memory cap.

## Deferred Ideas

- Background/async summarization (202 + poll) — sync is fine at this scale.
- Auto-attaching suggested tags — suggest-only this phase.
- Second specialized tagging model (qwen2.5:3b) — one model this phase.
- Cloud LLM (Anthropic), RAG, embeddings, related-notes, NL Q&A — Phase 6.
- Prebaking model into a custom Ollama image / GPU acceleration — prod concern (Phase 7).
