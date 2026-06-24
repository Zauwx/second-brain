"""Integration tests for Note CRUD endpoints.

Tests use the `client` fixture from conftest.py which:
  1. Creates a fresh in-memory SQLite database for each test.
  2. Overrides the `get_db` dependency with the SQLite session.
  3. Makes requests through httpx.AsyncClient (no live server required).

Coverage:
  - POST /notes → 201 with correct body
  - GET /notes/{id} → 200 with correct body
  - GET /notes/{id} → 404 for missing note
  - GET /notes → paginated response with correct structure
  - PUT /notes/{id} → 200 partial update
  - DELETE /notes/{id} → 204 No Content
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_note_returns_201(client: AsyncClient) -> None:
    """POST /notes with valid body should return 201 and the created note."""
    response = await client.post(
        "/notes",
        json={"title": "Test Note", "content": "Hello, world!", "source_url": None},
    )
    assert response.status_code == 201

    body = response.json()
    assert body["title"] == "Test Note"
    assert body["content"] == "Hello, world!"
    assert body["source_url"] is None
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_get_note_returns_200(client: AsyncClient) -> None:
    """GET /notes/{id} should return 200 and the note body after creation."""
    # Create a note first
    create_resp = await client.post(
        "/notes", json={"content": "Content for retrieval test"}
    )
    note_id = create_resp.json()["id"]

    response = await client.get(f"/notes/{note_id}")
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == note_id
    assert body["content"] == "Content for retrieval test"


@pytest.mark.asyncio
async def test_get_nonexistent_note_returns_404(client: AsyncClient) -> None:
    """GET /notes/99999 should return 404 when the note doesn't exist."""
    response = await client.get("/notes/99999")
    assert response.status_code == 404

    body = response.json()
    assert "detail" in body
    assert "99999" in body["detail"]


@pytest.mark.asyncio
async def test_list_notes_returns_paginated(client: AsyncClient) -> None:
    """GET /notes should return a paginated response with correct structure."""
    # Create 3 notes
    for i in range(3):
        await client.post("/notes", json={"content": f"Note number {i + 1}"})

    response = await client.get("/notes?page=1&page_size=10")
    assert response.status_code == 200

    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body

    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["items"]) == 3


@pytest.mark.asyncio
async def test_list_notes_pagination(client: AsyncClient) -> None:
    """GET /notes should respect page and page_size parameters."""
    # Create 5 notes
    for i in range(5):
        await client.post("/notes", json={"content": f"Pagination test note {i + 1}"})

    # First page with page_size=2
    resp_p1 = await client.get("/notes?page=1&page_size=2")
    assert resp_p1.status_code == 200
    body_p1 = resp_p1.json()
    assert body_p1["total"] == 5
    assert body_p1["page"] == 1
    assert body_p1["page_size"] == 2
    assert len(body_p1["items"]) == 2

    # Second page
    resp_p2 = await client.get("/notes?page=2&page_size=2")
    assert resp_p2.status_code == 200
    body_p2 = resp_p2.json()
    assert body_p2["page"] == 2
    assert len(body_p2["items"]) == 2

    # Third page has 1 remaining item
    resp_p3 = await client.get("/notes?page=3&page_size=2")
    assert resp_p3.status_code == 200
    body_p3 = resp_p3.json()
    assert len(body_p3["items"]) == 1


@pytest.mark.asyncio
async def test_update_note_returns_200(client: AsyncClient) -> None:
    """PUT /notes/{id} should return 200 with the updated note."""
    # Create
    create_resp = await client.post(
        "/notes",
        json={"title": "Original title", "content": "Original content"},
    )
    note_id = create_resp.json()["id"]

    # Update only the title (partial update)
    update_resp = await client.put(
        f"/notes/{note_id}", json={"title": "Updated title"}
    )
    assert update_resp.status_code == 200

    body = update_resp.json()
    assert body["id"] == note_id
    assert body["title"] == "Updated title"
    assert body["content"] == "Original content"  # unchanged


@pytest.mark.asyncio
async def test_update_nonexistent_note_returns_404(client: AsyncClient) -> None:
    """PUT /notes/99999 should return 404."""
    response = await client.put("/notes/99999", json={"title": "New title"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_note_returns_204(client: AsyncClient) -> None:
    """DELETE /notes/{id} should return 204 and the note should be gone."""
    # Create
    create_resp = await client.post("/notes", json={"content": "To be deleted"})
    note_id = create_resp.json()["id"]

    # Delete
    delete_resp = await client.delete(f"/notes/{note_id}")
    assert delete_resp.status_code == 204

    # Verify gone
    get_resp = await client.get(f"/notes/{note_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_note_returns_404(client: AsyncClient) -> None:
    """DELETE /notes/99999 should return 404."""
    response = await client.delete("/notes/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_note_requires_content(client: AsyncClient) -> None:
    """POST /notes without content should return 422 (validation error)."""
    response = await client.post("/notes", json={"title": "No content here"})
    assert response.status_code == 422
