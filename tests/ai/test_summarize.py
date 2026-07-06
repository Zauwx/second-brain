"""Integration tests for the summarize slice — AIL-01 coverage.

Tests verify:
  - POST /ai/summarize persists a 2-3 sentence summary via the (mocked) LLM
    provider and surfaces it on GET /notes/{id} (D-01, D-02, D-03, criterion 2).
  - Provider called exactly once with json_mode=False (summarize never needs
    structured JSON output).
  - Ollama unreachable → 503; note CRUD is unaffected (D-07).
  - A transient failure that recovers within the bounded retry still succeeds
    (D-08, retry boundary exercised at the provider-injection seam).
  - Cross-user ownership: 403 on another user's note, 404 on a missing note
    (Phase-3 contract, reused via NoteService.get_or_404_owned).

All tests use the FakeLLMProvider/ai_client seam from conftest.py — zero real
Ollama calls (D-10, criterion 5). No unittest.mock.

These tests are written BEFORE the implementation exists (TDD RED phase) —
they must fail now because POST /ai/summarize and Note.summary do not exist yet.
"""

import httpx

from app.core.dependencies import get_llm_provider
from app.main import app


class _RetryThenSucceedProvider:
    """Fake LLMProvider that raises ConnectionError once, then succeeds.

    Injected via the same app.dependency_overrides[get_llm_provider] mechanism
    as FakeLLMProvider — proves retry-then-succeed at the service/provider
    boundary without ever hitting a real network (D-08, D-10).
    """

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []
        self._raised_once = False

    async def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        if not self._raised_once:
            self._raised_once = True
            raise ConnectionError("mock: transient ollama blip")
        return self.response


async def test_summarize_persists_and_uses_mock_only(
    ai_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
    fake_llm_provider,
) -> None:
    """POST /ai/summarize persists the fake summary and surfaces it on GET."""
    fake_llm_provider.response = "This is a concise two-sentence summary. It covers the key point."

    create = await ai_client.post("/notes/", json={"content": "Long note text about async Python."})
    assert create.status_code == 201
    note_id = create.json()["id"]

    resp = await ai_client.post("/ai/summarize", json={"note_id": note_id})
    assert resp.status_code == 200

    assert len(fake_llm_provider.calls) == 1
    assert fake_llm_provider.calls[0][1] is False  # json_mode=False for summarize

    fetched = await ai_client.get(f"/notes/{note_id}")
    assert fetched.status_code == 200
    assert fetched.json()["summary"] == fake_llm_provider.response


async def test_ollama_down_returns_503(
    ai_client: httpx.AsyncClient,
    fake_llm_provider,
) -> None:
    """Ollama unreachable → 503; note CRUD (GET) still works (D-07)."""
    create = await ai_client.post("/notes/", json={"content": "A note that will fail to summarize."})
    assert create.status_code == 201
    note_id = create.json()["id"]

    fake_llm_provider.should_fail = True

    resp = await ai_client.post("/ai/summarize", json={"note_id": note_id})
    assert resp.status_code == 503

    fetched = await ai_client.get(f"/notes/{note_id}")
    assert fetched.status_code == 200


async def test_summarize_retries_then_succeeds(
    ai_client: httpx.AsyncClient,
) -> None:
    """A transient ConnectionError followed by success still yields 200 (D-08)."""
    retry_provider = _RetryThenSucceedProvider("Summary after one transient failure.")
    app.dependency_overrides[get_llm_provider] = lambda: retry_provider

    create = await ai_client.post("/notes/", json={"content": "Note content for retry test."})
    assert create.status_code == 201
    note_id = create.json()["id"]

    resp = await ai_client.post("/ai/summarize", json={"note_id": note_id})
    assert resp.status_code == 200

    fetched = await ai_client.get(f"/notes/{note_id}")
    assert fetched.json()["summary"] == "Summary after one transient failure."


async def test_summarize_forbidden_wrong_owner(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B summarizing user A's note returns 403 (Phase-3 contract)."""
    a_note = (
        await user_a_client.post("/notes/", json={"content": "A's private note content."})
    ).json()
    assert "id" in a_note

    resp = await user_b_client.post("/ai/summarize", json={"note_id": a_note["id"]})
    assert resp.status_code == 403


async def test_summarize_missing_note_404(auth_client: httpx.AsyncClient) -> None:
    """Summarizing a non-existent note id returns 404."""
    resp = await auth_client.post("/ai/summarize", json={"note_id": 999999})
    assert resp.status_code == 404
