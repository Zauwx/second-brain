"""Integration tests for the Collections domain (ORG-03, ORG-04).

Tests prove:
  - POST /collections/ → 201 with id and name
  - POST /collections/{id}/notes → 204 (add note to collection)
  - GET /collections/{id}/notes → 200 NoteListResponse envelope (items/total/pages)
  - GET /collections/ → lists the caller's collections only
  - DELETE /collections/{id}/notes/{note_id} → 204; note disappears from listing
  - Cross-user isolation: user B cannot access user A's collection (403); missing → 404
  - A note can belong to multiple collections (many-to-many)

Uses `auth_client` for single-user tests and `user_a_client`/`user_b_client` for isolation.
"""

import httpx


# ---------------------------------------------------------------------------
# Create collection
# ---------------------------------------------------------------------------


async def test_create_collection_returns_201(auth_client: httpx.AsyncClient) -> None:
    """POST /collections/ with a valid name should return 201 and the collection body."""
    resp = await auth_client.post("/collections/", json={"name": "Work"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Work"
    assert "id" in data
    assert "user_id" in data


# ---------------------------------------------------------------------------
# List collections
# ---------------------------------------------------------------------------


async def test_list_collections_returns_own(auth_client: httpx.AsyncClient) -> None:
    """GET /collections/ must return the caller's collections."""
    await auth_client.post("/collections/", json={"name": "Books"})
    resp = await auth_client.get("/collections/")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Books" in names


# ---------------------------------------------------------------------------
# Add note and list collection notes (NoteListResponse envelope)
# ---------------------------------------------------------------------------


async def test_list_collection_notes_returns_envelope(auth_client: httpx.AsyncClient) -> None:
    """GET /collections/{id}/notes should return the NoteListResponse envelope."""
    coll_resp = await auth_client.post("/collections/", json={"name": "Reading"})
    assert coll_resp.status_code == 201
    coll = coll_resp.json()

    note_resp = await auth_client.post("/notes/", json={"content": "for collection test"})
    assert note_resp.status_code == 201
    note = note_resp.json()

    add_resp = await auth_client.post(
        f"/collections/{coll['id']}/notes", json={"note_id": note["id"]}
    )
    assert add_resp.status_code == 204

    list_resp = await auth_client.get(f"/collections/{coll['id']}/notes")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data
    assert "page" in data
    assert "size" in data
    assert any(i["id"] == note["id"] for i in data["items"])


# ---------------------------------------------------------------------------
# Remove note from collection
# ---------------------------------------------------------------------------


async def test_remove_note_from_collection(auth_client: httpx.AsyncClient) -> None:
    """DELETE /collections/{id}/notes/{note_id} should remove the note from the collection."""
    coll = (await auth_client.post("/collections/", json={"name": "Temp"})).json()
    note = (await auth_client.post("/notes/", json={"content": "to remove"})).json()

    # Add the note
    await auth_client.post(f"/collections/{coll['id']}/notes", json={"note_id": note["id"]})

    # Verify it's there
    before = await auth_client.get(f"/collections/{coll['id']}/notes")
    assert any(i["id"] == note["id"] for i in before.json()["items"])

    # Remove it
    del_resp = await auth_client.delete(f"/collections/{coll['id']}/notes/{note['id']}")
    assert del_resp.status_code == 204

    # Verify it's gone
    after = await auth_client.get(f"/collections/{coll['id']}/notes")
    assert after.status_code == 200
    assert not any(i["id"] == note["id"] for i in after.json()["items"])


# ---------------------------------------------------------------------------
# Many-to-many: one note in multiple collections
# ---------------------------------------------------------------------------


async def test_note_can_belong_to_multiple_collections(auth_client: httpx.AsyncClient) -> None:
    """A single note can be added to multiple collections (many-to-many)."""
    coll_a = (await auth_client.post("/collections/", json={"name": "Alpha"})).json()
    coll_b = (await auth_client.post("/collections/", json={"name": "Beta"})).json()
    note = (await auth_client.post("/notes/", json={"content": "shared note"})).json()

    r1 = await auth_client.post(f"/collections/{coll_a['id']}/notes", json={"note_id": note["id"]})
    r2 = await auth_client.post(f"/collections/{coll_b['id']}/notes", json={"note_id": note["id"]})
    assert r1.status_code == 204
    assert r2.status_code == 204

    notes_a = (await auth_client.get(f"/collections/{coll_a['id']}/notes")).json()["items"]
    notes_b = (await auth_client.get(f"/collections/{coll_b['id']}/notes")).json()["items"]
    assert any(i["id"] == note["id"] for i in notes_a)
    assert any(i["id"] == note["id"] for i in notes_b)


# ---------------------------------------------------------------------------
# Cross-user isolation (ORG-04, T-04-iso)
# ---------------------------------------------------------------------------


async def test_collection_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B cannot access user A's collection — must get 403 (exists) or 404 (missing)."""
    # User A creates a collection and a note
    coll_resp = await user_a_client.post("/collections/", json={"name": "A's Secret Collection"})
    assert coll_resp.status_code == 201
    coll_id = coll_resp.json()["id"]

    note_resp = await user_a_client.post("/notes/", json={"content": "A's private note"})
    assert note_resp.status_code == 201
    note_id = note_resp.json()["id"]

    await user_a_client.post(f"/collections/{coll_id}/notes", json={"note_id": note_id})

    # User B tries to list A's collection notes → 403
    resp_list = await user_b_client.get(f"/collections/{coll_id}/notes")
    assert resp_list.status_code == 403

    # User B tries to add a note to A's collection → must fail (403)
    b_note = (await user_b_client.post("/notes/", json={"content": "B's note"})).json()
    resp_add = await user_b_client.post(
        f"/collections/{coll_id}/notes", json={"note_id": b_note["id"]}
    )
    assert resp_add.status_code == 403

    # Missing collection id → 404
    resp_missing = await user_b_client.get("/collections/999999/notes")
    assert resp_missing.status_code == 404

    # User B's collection list must NOT contain A's collections
    b_collections_resp = await user_b_client.get("/collections/")
    assert b_collections_resp.status_code == 200
    b_coll_ids = [c["id"] for c in b_collections_resp.json()]
    assert coll_id not in b_coll_ids
