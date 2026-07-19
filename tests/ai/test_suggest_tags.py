"""Integration tests for the suggest-tags slice — AIL-02 coverage.

Tests verify:
  - POST /ai/suggest-tags returns a JSON list of tag strings from the (mocked)
    LLM provider, called with format=TAG_SCHEMA (an explicit JSON schema, not
    the bare "json" mode string — see 260720-1ng root-cause fix).
  - suggest-tags is suggest-only — it neither attaches tags nor persists a
    summary on the note (D-04); GET /notes/{id} is unchanged.
  - _parse_tag_list (unit, no HTTP) handles a dict-wrapped response, a
    prose-polluted response, and garbage without ever raising.
  - An unparseable non-empty model output emits a structured WARNING and
    still returns 200 with [] (260720-1ng observability fix).
  - Cross-user ownership: 403 on another user's note, 404 on a missing note
    (Phase-3 contract, reused via NoteService.get_or_404_owned).
  - Ollama unreachable → 503 (D-07), identical to summarize.

All HTTP tests use the FakeLLMProvider/ai_client seam from conftest.py — zero
real Ollama calls (D-10, criterion 5). No unittest.mock.

These tests are written BEFORE the implementation exists (TDD RED phase) —
they must fail now because POST /ai/suggest-tags and _parse_tag_list do not
exist yet.
"""

import logging

import httpx

from app.ai.service import TAG_SCHEMA, _parse_tag_list


async def test_suggest_tags_returns_list_only(
    ai_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
    fake_llm_provider,
) -> None:
    """POST /ai/suggest-tags returns the parsed tag list; suggest-only (D-04)."""
    fake_llm_provider.response = '["python","docker"]'

    create = await ai_client.post(
        "/notes/", json={"content": "A note about Python and Docker tooling."}
    )
    assert create.status_code == 201
    note_id = create.json()["id"]

    resp = await ai_client.post("/ai/suggest-tags", json={"note_id": note_id})
    assert resp.status_code == 200
    assert resp.json() == {"tags": ["python", "docker"]}

    assert len(fake_llm_provider.calls) == 1
    assert fake_llm_provider.calls[0][1] == TAG_SCHEMA  # explicit schema for suggest-tags

    fetched = await ai_client.get(f"/notes/{note_id}")
    assert fetched.status_code == 200
    assert fetched.json()["tags"] == []  # nothing attached (D-04)
    assert fetched.json()["summary"] is None  # nothing persisted (D-04)


def test_parse_tag_list_lenient_variants() -> None:
    """_parse_tag_list never raises on malformed model output (D-05)."""
    assert _parse_tag_list('{"tags": ["a", "b"]}') == ["a", "b"]
    assert _parse_tag_list('Here are tags: ["a","b"] hope that helps') == ["a", "b"]
    assert _parse_tag_list("not json") == []


async def test_parse_failure_logs_warning(
    ai_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
    fake_llm_provider,
    caplog,
) -> None:
    """An unparseable non-empty model output logs a WARNING but still returns 200/[] (D-05)."""
    # Real-world failure payload observed live: format="json" makes the model
    # mimic the (now-removed) prompt example as object KEYS instead of a list.
    fake_llm_provider.response = '{"tag-one": "language-models", "tag-two": "nlp-techniques"}'

    create = await ai_client.post(
        "/notes/", json={"content": "A note about language models and NLP techniques."}
    )
    assert create.status_code == 201
    note_id = create.json()["id"]

    with caplog.at_level(logging.WARNING, logger="app.ai.service"):
        resp = await ai_client.post("/ai/suggest-tags", json={"note_id": note_id})

    assert resp.status_code == 200
    assert resp.json() == {"tags": []}

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    assert warning_records[0].levelname == "WARNING"
    assert "tag-one" in warning_records[0].raw


async def test_suggest_tags_forbidden_wrong_owner(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B suggesting tags on user A's note returns 403 (Phase-3 contract)."""
    a_note = (
        await user_a_client.post("/notes/", json={"content": "A's private note content."})
    ).json()
    assert "id" in a_note

    resp = await user_b_client.post("/ai/suggest-tags", json={"note_id": a_note["id"]})
    assert resp.status_code == 403


async def test_suggest_tags_missing_note_404(auth_client: httpx.AsyncClient) -> None:
    """Suggesting tags for a non-existent note id returns 404."""
    resp = await auth_client.post("/ai/suggest-tags", json={"note_id": 999999})
    assert resp.status_code == 404


async def test_suggest_tags_ollama_down_503(
    ai_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
    fake_llm_provider,
) -> None:
    """Ollama unreachable → 503; note CRUD (GET) still works (D-07)."""
    create = await ai_client.post(
        "/notes/", json={"content": "A note that will fail to get tags."}
    )
    assert create.status_code == 201
    note_id = create.json()["id"]

    fake_llm_provider.should_fail = True

    resp = await ai_client.post("/ai/suggest-tags", json={"note_id": note_id})
    assert resp.status_code == 503

    fetched = await ai_client.get(f"/notes/{note_id}")
    assert fetched.status_code == 200
