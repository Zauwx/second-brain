"""Opt-in live regression test for the suggest-tags fix (260720-1ng).

This module is EXCLUDED from the default `pytest tests/` run (D-10: the
default suite must stay hermetic — zero real Ollama calls). It is registered
under the `live_ollama` marker and only runs when explicitly selected:

    uv run pytest -m live_ollama -v

Requires the full docker compose stack to be up (api, mysql, ollama) with
llama3.2:3b already pulled, and the api container reachable at
http://localhost:8000. It drives the REAL model through the live API — the
mocked FakeLLMProvider seam is structurally blind to this class of failure
(it never exercises real model behavior under the production `format=`
value), which is precisely how the empty-tag-list defect reached a live
checkpoint through a 128-green mocked suite.

Assertions intentionally avoid pinning exact tag values — model output is
non-deterministic. They instead guard the two concrete regressions this task
fixes: an empty list, and a `tag-` prefix artifact copied from the (now
removed) prompt example.
"""

import uuid

import httpx
import pytest

pytestmark = pytest.mark.live_ollama


async def test_suggest_tags_live_returns_nonempty_unprefixed_tags() -> None:
    """POST /ai/suggest-tags against the real stack returns real, unprefixed tags."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=180.0) as client:
        unique = uuid.uuid4().hex[:8]
        email = f"live-{unique}@example.com"
        password = "Passw0rd!"

        register = await client.post(
            "/auth/register", json={"email": email, "password": password}
        )
        assert register.status_code == 201, register.text

        login = await client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        note_content = (
            "Retrieval-augmented generation (RAG) combines a vector database of "
            "embedded document chunks with a large language model. At query time, "
            "the system embeds the user's question, retrieves the most similar "
            "chunks by cosine similarity, and feeds them into the model's prompt "
            "as grounding context before generating an answer."
        )
        create = await client.post(
            "/notes/", json={"content": note_content}, headers=headers
        )
        assert create.status_code == 201, create.text
        note_id = create.json()["id"]

        resp = await client.post(
            "/ai/suggest-tags", json={"note_id": note_id}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        tags = resp.json()["tags"]

        assert isinstance(tags, list)
        assert len(tags) >= 1
        assert all(isinstance(t, str) and t for t in tags)
        assert not any(t.startswith("tag-") for t in tags)

        fetched = await client.get(f"/notes/{note_id}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["tags"] == []  # suggest-only preserved (D-04)
