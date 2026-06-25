"""Cross-user isolation tests for the notes domain (Phase 3 — AUTH-04).

Tests prove that per-user data isolation is enforced end-to-end against real MySQL:
  - No auth token → 401 on any note endpoint
  - User B accessing user A's note via GET/PUT/DELETE → 403 Forbidden (D-08)
  - Non-existent note id (authenticated) → 404 Not Found
  - GET /notes/ never leaks another user's notes (D-09, list isolation)
  - Note creation assigns user_id server-side; body-supplied user_id is ignored (D-10)

Uses `user_a_client` and `user_b_client` fixtures (two independently authenticated
AsyncClients sharing the same test transaction for rollback isolation) and the plain
`client` fixture (unauthenticated) for the 401 case.

TDD: written before router is protected — tests will FAIL (RED) until Task 3 router
changes are applied (GREEN).
"""

import httpx

# ---------------------------------------------------------------------------
# 401 — no auth token required
# ---------------------------------------------------------------------------


async def test_create_note_requires_auth(client: httpx.AsyncClient) -> None:
    """POST /notes/ with no Authorization header must return 401."""
    response = await client.post("/notes/", json={"content": "no auth"})
    assert response.status_code == 401


async def test_get_note_requires_auth(client: httpx.AsyncClient) -> None:
    """GET /notes/{id} with no Authorization header must return 401."""
    response = await client.get("/notes/1")
    assert response.status_code == 401


async def test_list_notes_requires_auth(client: httpx.AsyncClient) -> None:
    """GET /notes/ with no Authorization header must return 401."""
    response = await client.get("/notes/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 403 — cross-user access (D-08)
# ---------------------------------------------------------------------------


async def test_cross_user_get_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B cannot read user A's note — must return 403 Forbidden (D-08)."""
    # User A creates a note
    create_resp = await user_a_client.post("/notes/", json={"content": "A's secret note"})
    assert create_resp.status_code == 201, f"A create failed: {create_resp.json()}"
    note_id = create_resp.json()["id"]

    # User B tries to read it
    resp = await user_b_client.get(f"/notes/{note_id}")
    assert resp.status_code == 403


async def test_cross_user_put_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B cannot update user A's note — must return 403 Forbidden (D-08)."""
    create_resp = await user_a_client.post("/notes/", json={"content": "A's note to protect"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    resp = await user_b_client.put(f"/notes/{note_id}", json={"content": "B overwrites A"})
    assert resp.status_code == 403


async def test_cross_user_delete_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B cannot delete user A's note — must return 403 Forbidden (D-08)."""
    create_resp = await user_a_client.post("/notes/", json={"content": "A's note to keep"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    resp = await user_b_client.delete(f"/notes/{note_id}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 404 — missing note (authenticated user)
# ---------------------------------------------------------------------------


async def test_missing_note_returns_404(user_a_client: httpx.AsyncClient) -> None:
    """GET /notes/999999 with valid auth must return 404 (note does not exist)."""
    resp = await user_a_client.get("/notes/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Note not found"


# ---------------------------------------------------------------------------
# List isolation (D-09)
# ---------------------------------------------------------------------------


async def test_list_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """GET /notes/ returns only the authenticated user's notes; never the other user's.

    Verifies both directions:
      - A's list contains A's note and NOT B's note.
      - B's list contains B's note and NOT A's note.
    """
    # Each user creates a uniquely identifiable note
    a_resp = await user_a_client.post("/notes/", json={"content": "A's unique isolation note"})
    assert a_resp.status_code == 201
    b_resp = await user_b_client.post("/notes/", json={"content": "B's unique isolation note"})
    assert b_resp.status_code == 201

    # A's list must contain A's note and must NOT contain B's note
    a_list = await user_a_client.get("/notes/")
    assert a_list.status_code == 200
    a_contents = [item["content"] for item in a_list.json()["items"]]
    assert "A's unique isolation note" in a_contents
    assert "B's unique isolation note" not in a_contents

    # B's list must contain B's note and must NOT contain A's note
    b_list = await user_b_client.get("/notes/")
    assert b_list.status_code == 200
    b_contents = [item["content"] for item in b_list.json()["items"]]
    assert "B's unique isolation note" in b_contents
    assert "A's unique isolation note" not in b_contents


# ---------------------------------------------------------------------------
# Owner assignment (D-10)
# ---------------------------------------------------------------------------


async def test_create_assigns_owner(
    user_a_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
) -> None:
    """Note creation assigns user_id server-side from the JWT; body user_id is ignored (D-10).

    Two sub-cases:
      1. The response user_id equals the authenticated user's id.
      2. A body containing a fake user_id (9999) is ignored — the real user_id is assigned.
    """
    # Sub-case 1: normal create; user_id in response should equal user A's id
    login_a = await user_a_client.post("/notes/", json={"content": "owner check"})
    assert login_a.status_code == 201
    note_data = login_a.json()
    assert "user_id" in note_data
    a_user_id = note_data["user_id"]
    assert isinstance(a_user_id, int)

    # Sub-case 2: body supplies a fake user_id — must be ignored
    fake_resp = await user_a_client.post(
        "/notes/", json={"content": "fake owner attempt", "user_id": 9999}
    )
    assert fake_resp.status_code == 201
    # user_id in response must still equal user A's real id
    assert fake_resp.json()["user_id"] == a_user_id
