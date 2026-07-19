# Quick Task 260720-1ng: fix: suggest-tags returns empty list — replace format="json" with an explicit JSON schema - Context

**Gathered:** 2026-07-19
**Status:** Ready for planning

<domain>
## Task Boundary

`POST /ai/suggest-tags` returns HTTP 200 with `{"tags": []}` against the real stack, for every note.

Root cause (empirically confirmed during the Phase 05 live checkpoint, 05-04 Task 3):
`AIService.suggest_tags` calls the provider with `json_mode=True`, which `OllamaProvider.complete`
maps to `format="json"`. Under that grammar constraint llama3.2:3b emits an **object**, and it
mimics the placeholder example in `build_tag_prompt` (`["tag-one", "tag-two"]`) by turning those
literals into **keys**:

```
json_mode=True  -> '{"tag-one": "language-models", "tag-two": "nlp-techniques", ...}'
json_mode=False -> '["rags", "vector-embeddings", "knowledge-store"]'
```

`_parse_tag_list` unwraps a dict only when one of its **values is a list**. Here every value is a
string, so no branch matches, `data` stays a dict, `not isinstance(data, list)` is true, and the
function returns `[]`. HTTP 200, empty list, nothing logged.

Verified fix (3/3 clean runs against the live model): pass an explicit JSON schema as `format=`
instead of the string `"json"`:

```
format=<schema> -> '{"tags": ["rag", "retrieval", "augmented-generation"]}'
```

That shape is already handled correctly by the EXISTING `_parse_tag_list` dict-unwrap (the `tags`
value IS a list) — so the parser itself needs no change for the happy path.

</domain>

<decisions>
## Implementation Decisions

### Provider API shape — LOCKED
Replace the `json_mode: bool` keyword with a pass-through `format` parameter on the provider seam:

```python
# app/ai/providers/protocol.py
async def complete(self, prompt: str, *, format: str | dict = "") -> str: ...
```

- `OllamaProvider.complete` forwards `format` straight to `AsyncClient.chat(format=...)`.
  The existing `format="json" if json_mode else ""` expression goes away entirely.
- The caller owns the schema. Define it in the AI domain (service or schemas module), NOT in the
  provider — the transport layer must not know about tagging.
- Rationale: a bool cannot carry a schema. This keeps the seam honest about what it actually does
  and leaves room for the future Anthropic provider to map a schema onto tool-use / JSON mode.
- Consequence: `protocol.py`, `ollama.py`, and every test fake implementing the protocol must be
  updated to the new signature. `json_mode` must not survive anywhere.

### Tag schema — LOCKED
```python
{
  "type": "object",
  "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
  "required": ["tags"],
}
```
Object-wrapped (not a bare array) because that is the shape empirically verified 3/3 against the
live model, and the existing parser already unwraps it.

### Parse-failure observability — LOCKED
Keep the lenient contract — still return `[]` with HTTP 200 (a failed tag suggestion must not break
the caller). But when parsing yields an empty list from **non-empty** raw output, emit a structured
warning including the raw text truncated (~200 chars):

```python
tags = _parse_tag_list(raw)
if not tags and raw.strip():
    logger.warning("suggest_tags: unparseable model output", extra={"raw": raw[:200]})
return tags
```
Rationale: silence is precisely why this defect survived a 128-green suite and reached the live
checkpoint. Do NOT convert this to a 502 — a 3B model will occasionally misbehave in normal
operation and that should degrade, not fail.

### Regression protection — LOCKED
Add an opt-in live test that exercises the real model:
- Marker `live_ollama` registered in `pyproject.toml`.
- Default run excludes it (`addopts = "-m 'not live_ollama'"` or equivalent), so `pytest tests/`
  stays fully hermetic — Phase 05 criterion 5 / D-10 ("zero real Ollama calls in the suite") must
  remain true and must still report the existing 128 passing.
- `pytest -m live_ollama` runs it against a live stack; it asserts a non-empty list of non-empty
  strings, NOT exact tag values (model output is non-deterministic).
- Rationale: the mocked provider seam is structurally blind to this failure class — fakes feed the
  parser hand-written strings, so the suite verified imagined output, never real model behavior
  under the production flag.

### Claude's Discretion
- Exact wording of `build_tag_prompt`. The current literal example `["tag-one", "tag-two"]` is
  actively harmful — the model copies it verbatim (as keys under `format="json"`, and as a literal
  `tag-` prefix on real tags in 2 of 3 runs under `format=""`). Reword or drop the example; the
  schema now carries the shape contract, so the prompt no longer needs to demonstrate it.
- Where `TAG_SCHEMA` lives (service module vs `app/ai/schemas.py`) — follow existing conventions.
- Logger acquisition style — match whatever the codebase already does.

</decisions>

<specifics>
## Specific Ideas

Empirical evidence gathered during the checkpoint, reproducible via the api container:

```
format=""       -> '["tag-rag", "tag-vector-embeddings", "tag-hallucination-reduction"]'  (2/3 runs polluted with the tag- prefix)
format="json"   -> '{"tag-one": "language-models", "tag-two": "nlp-techniques", ...}'      (parses to [] — the bug)
format=<schema> -> '{"tags": ["rag", "retrieval", "augmented-generation"]}'                (3/3 clean)
```

Acceptance for this task — verified against the LIVE stack, not just mocks:
1. `POST /ai/suggest-tags {"note_id": N}` returns 200 with a non-empty list of tag strings.
2. Tags carry no `tag-` prefix artifacts from the prompt example.
3. Suggest-only is preserved (D-04): the note's own `tags` array stays empty — the endpoint must
   still have no write path.
4. `pytest tests/` remains hermetic and green (128 passing, no real Ollama calls).
5. `docker compose exec api ...` / `POST /ai/summarize` still works — the `format` signature change
   must not regress the plain-text summarize path (it passes no format).

</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/05-local-ai-ollama/05-04-SUMMARY.md` — the plan whose Task 3 checkpoint surfaced this.
- `.planning/STATE.md` Blockers/Concerns — records this as BLOCKING for Phase 05 sign-off.
- `.planning/phases/05-local-ai-ollama/05-RESEARCH.md` Pattern 4 — origin of the lenient `_parse_tag_list`.
- Decisions referenced: D-04 (suggest-only), D-05 (tag prompt / lenient parse), D-06 (provider seam),
  D-07 (503 translation, unaffected), D-10 (no real Ollama in the default suite).

</canonical_refs>
