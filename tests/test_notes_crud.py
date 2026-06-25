"""End-to-end CRUD tests for Note endpoints against real MySQL (D-16, D-17, D-18).

Uses the `client` fixture from conftest.py which:
  1. Spins up an ephemeral mysql:8.4 container (once per session).
  2. Builds the schema via `alembic upgrade head` — verifies migrations.
  3. Wraps each test in a transaction that is rolled back at teardown.
  4. Injects the test session via `app.dependency_overrides[get_db]`.

No DB mocks. Every assertion exercises the real MySQL stack end-to-end.

Coverage:
  - POST /notes/ → 201 with correct body
  - POST /notes/ with source_url → 201 source_url echoed
  - POST /notes/ missing content → 422 validation error
  - GET /notes/{id} → 200 with correct body
  - GET /notes/999999 → 404 with detail "Note not found"
  - PUT /notes/{id} → 200 partial update, updated_at >= created_at
  - DELETE /notes/{id} → 204 No Content; subsequent GET → 404
  - GET /notes/ → 200 with envelope keys {items, total, page, size, pages}
  - GET /notes/?size=101 → 422 (size capped at 100)
  - OpenAPI: /openapi.json includes /notes/ and /notes/{note_id} paths
"""

import httpx


async def test_create_note_returns_201(auth_client: httpx.AsyncClient) -> None:
    """POST /notes/ with valid body should return 201 and the created note."""
    response = await auth_client.post("/notes/", json={"content": "hello"})
    assert response.status_code == 201

    data = response.json()
    assert data["content"] == "hello"
    assert "id" in data
    assert "created_at" in data


async def test_create_note_with_source_url(auth_client: httpx.AsyncClient) -> None:
    """POST /notes/ with source_url should echo it back in the response."""
    response = await auth_client.post(
        "/notes/", json={"content": "x", "source_url": "https://e.com"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_url"] == "https://e.com"


async def test_create_note_missing_content_returns_422(auth_client: httpx.AsyncClient) -> None:
    """POST /notes/ without content should return 422 (FastAPI validation)."""
    response = await auth_client.post("/notes/", json={"title": "No content"})
    assert response.status_code == 422


async def test_get_note_returns_200(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/{id} should return 200 and the note body after creation."""
    create_resp = await auth_client.post("/notes/", json={"content": "Content for retrieval test"})
    note_id = create_resp.json()["id"]

    response = await auth_client.get(f"/notes/{note_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == note_id
    assert data["content"] == "Content for retrieval test"


async def test_get_nonexistent_note_returns_404(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/999999 should return 404 with detail 'Note not found'."""
    response = await auth_client.get("/notes/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_update_note_returns_200(auth_client: httpx.AsyncClient) -> None:
    """PUT /notes/{id} should return 200 with updated content."""
    create_resp = await auth_client.post("/notes/", json={"content": "original"})
    note_id = create_resp.json()["id"]
    created_at = create_resp.json()["created_at"]

    update_resp = await auth_client.put(f"/notes/{note_id}", json={"content": "edited"})
    assert update_resp.status_code == 200

    data = update_resp.json()
    assert data["content"] == "edited"
    assert data["updated_at"] >= created_at


async def test_delete_note_returns_204_then_404(auth_client: httpx.AsyncClient) -> None:
    """DELETE /notes/{id} should return 204; subsequent GET should return 404."""
    create_resp = await auth_client.post("/notes/", json={"content": "To be deleted"})
    note_id = create_resp.json()["id"]

    delete_resp = await auth_client.delete(f"/notes/{note_id}")
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    get_resp = await auth_client.get(f"/notes/{note_id}")
    assert get_resp.status_code == 404


async def test_list_notes_returns_envelope(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/ should return 200 with envelope keys {items,total,page,size,pages}."""
    response = await auth_client.get("/notes/")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert "pages" in data


async def test_list_notes_oversized_page_returns_422(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?size=101 should return 422 (size bounded at 100 via Query le=100)."""
    response = await auth_client.get("/notes/?size=101")
    assert response.status_code == 422


async def test_openapi_includes_notes_paths(auth_client: httpx.AsyncClient) -> None:
    """GET /openapi.json should include /notes/ and /notes/{note_id} paths."""
    response = await auth_client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    assert "/notes/" in paths
    assert "/notes/{note_id}" in paths

    notes_list = paths["/notes/"]
    assert "post" in notes_list
    assert "get" in notes_list

    notes_item = paths["/notes/{note_id}"]
    assert "get" in notes_item
    assert "put" in notes_item
    assert "delete" in notes_item
