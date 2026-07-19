"""Integration tests for the Tags domain — ORG-01 coverage.

Tests verify:
  - POST /notes/{id}/tags attaches a tag and returns NoteRead with the tag in `tags`
  - find-or-create is idempotent: same name twice creates only one tag
  - Tag name normalization: "Python", " python " → same stored tag "python"
  - GET /tags lists only the caller's own tags
  - DELETE /notes/{id}/tags/{name} detaches a tag (204)
  - Cross-user isolation: user A's tags are invisible to user B; B cannot tag A's note

All tests run against real MySQL via conftest.py testcontainer fixtures.
These tests are written BEFORE the implementation exists (TDD RED phase).
"""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


async def test_attach_tag_persists_across_sessions(
    ft_auth_client: httpx.AsyncClient,
    test_engine,
) -> None:
    """CR-01 regression: an attached tag is COMMITTED and survives in a NEW session.

    This is the multi-request guarantee. The attach is performed via the committed
    (ft_*) session, then the note_tags / tags rows are re-read through a brand-new
    independent session opened directly on the engine. If TagRepository.attach only
    flushed (the CR-01 bug), the INSERTs would be rolled back on request teardown
    and the fresh session would see no tag — failing this test. A bare rollback
    fixture cannot catch this regression, which is why it runs on committed data.
    """
    create = await ft_auth_client.post("/notes/", json={"content": "persisted tag note"})
    assert create.status_code == 201
    note_id = create.json()["id"]

    attach = await ft_auth_client.post(f"/notes/{note_id}/tags", json={"name": "persisted"})
    assert attach.status_code == 200

    # Re-read via a brand-new session — proves the write was committed, not just flushed.
    fresh_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with fresh_factory() as fresh:
        rows = (
            await fresh.execute(
                text(
                    "SELECT t.name FROM tags t "
                    "JOIN note_tags nt ON nt.tag_id = t.id "
                    "WHERE nt.note_id = :nid"
                ),
                {"nid": note_id},
            )
        ).scalars().all()
    assert "persisted" in rows, (
        f"Attached tag must persist across sessions (CR-01), got: {rows}"
    )


async def test_attach_tag_returns_200_with_tags_array(auth_client: httpx.AsyncClient) -> None:
    """POST /notes/{id}/tags returns 200 NoteRead with the tag in the tags array."""
    # Setup: create a note
    create_resp = await auth_client.post("/notes/", json={"content": "tagging test note"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    # Action: attach tag
    resp = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "python"})
    assert resp.status_code == 200

    # Assert: note response carries the tags array with the attached tag
    data = resp.json()
    assert "tags" in data, "Response must include a 'tags' array"
    assert any(t["name"] == "python" for t in data["tags"]), (
        f"Expected 'python' in tags, got: {data['tags']}"
    )


async def test_find_or_create_idempotent(auth_client: httpx.AsyncClient) -> None:
    """Attaching the same tag name twice reuses one tag (find-or-create)."""
    # Setup: create a note
    create_resp = await auth_client.post("/notes/", json={"content": "idempotency test"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    # Action: attach the same tag twice
    resp1 = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "docker"})
    assert resp1.status_code == 200
    resp2 = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "docker"})
    assert resp2.status_code == 200

    # Assert: note has exactly one "docker" tag (not two duplicates)
    data = resp2.json()
    tag_names = [t["name"] for t in data["tags"]]
    assert tag_names.count("docker") == 1, (
        f"Expected exactly one 'docker' tag, got: {tag_names}"
    )

    # Assert: GET /tags also shows only one "docker" tag
    tags_resp = await auth_client.get("/tags")
    assert tags_resp.status_code == 200
    all_names = [t["name"] for t in tags_resp.json()]
    assert all_names.count("docker") == 1, (
        f"Expected exactly one 'docker' in GET /tags, got: {all_names}"
    )


async def test_tag_normalization(auth_client: httpx.AsyncClient) -> None:
    """'Python', 'PYTHON', and ' python ' all map to the same normalized tag 'python'."""
    # Setup: create a note
    create_resp = await auth_client.post("/notes/", json={"content": "normalization test"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    # Attach three variants of the same name
    r1 = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "Python"})
    assert r1.status_code == 200
    r2 = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "PYTHON"})
    assert r2.status_code == 200
    r3 = await auth_client.post(f"/notes/{note_id}/tags", json={"name": " python "})
    assert r3.status_code == 200

    # Only one "python" tag should exist
    data = r3.json()
    tag_names = [t["name"] for t in data["tags"]]
    assert tag_names.count("python") == 1, (
        f"Expected exactly one normalized 'python' tag, got: {tag_names}"
    )
    # The stored name must be lowercase + stripped
    assert "python" in tag_names


async def test_list_tags_returns_only_own_tags(auth_client: httpx.AsyncClient) -> None:
    """GET /tags returns only the authenticated user's tags."""
    # Setup: create a note and attach a couple of tags
    create_resp = await auth_client.post("/notes/", json={"content": "list tags test"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    await auth_client.post(f"/notes/{note_id}/tags", json={"name": "fastapi"})
    await auth_client.post(f"/notes/{note_id}/tags", json={"name": "mysql"})

    # Action: list tags
    resp = await auth_client.get("/tags")
    assert resp.status_code == 200

    # Assert: response is a list containing the attached tags
    tag_names = [t["name"] for t in resp.json()]
    assert "fastapi" in tag_names
    assert "mysql" in tag_names


async def test_detach_tag_returns_204(auth_client: httpx.AsyncClient) -> None:
    """DELETE /notes/{id}/tags/{name} detaches a tag and returns 204."""
    # Setup: create note and attach tag
    create_resp = await auth_client.post("/notes/", json={"content": "detach test note"})
    assert create_resp.status_code == 201
    note_id = create_resp.json()["id"]

    attach_resp = await auth_client.post(f"/notes/{note_id}/tags", json={"name": "todelete"})
    assert attach_resp.status_code == 200
    assert any(t["name"] == "todelete" for t in attach_resp.json()["tags"])

    # Action: detach the tag
    delete_resp = await auth_client.delete(f"/notes/{note_id}/tags/todelete")
    assert delete_resp.status_code == 204
    assert delete_resp.content == b""

    # Assert: the tag is no longer on the note
    get_resp = await auth_client.get(f"/notes/{note_id}")
    assert get_resp.status_code == 200
    tag_names = [t["name"] for t in get_resp.json()["tags"]]
    assert "todelete" not in tag_names, (
        f"Tag 'todelete' should be removed, got: {tag_names}"
    )


async def test_attach_tag_unauthorized_returns_401(client: httpx.AsyncClient) -> None:
    """POST /notes/{id}/tags without auth returns 401."""
    resp = await client.post("/notes/1/tags", json={"name": "unauthorized"})
    assert resp.status_code == 401


async def test_attach_tag_to_missing_note_returns_404(auth_client: httpx.AsyncClient) -> None:
    """POST /notes/999999/tags on a non-existent note returns 404."""
    resp = await auth_client.post("/notes/999999/tags", json={"name": "ghost"})
    assert resp.status_code == 404


async def test_tag_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User A's tags are never visible to user B.

    - User B's GET /tags never contains a tag created by user A.
    - User B cannot attach a tag to user A's note (403).
    """
    # User A creates a note and attaches a tag
    a_note = (await user_a_client.post("/notes/", json={"content": "A's private note"})).json()
    assert "id" in a_note
    tag_resp = await user_a_client.post(
        f"/notes/{a_note['id']}/tags", json={"name": "a-secret-tag"}
    )
    assert tag_resp.status_code == 200

    # User B's tag list must NOT include A's tag
    b_tags_resp = await user_b_client.get("/tags")
    assert b_tags_resp.status_code == 200
    b_tag_names = [t["name"] for t in b_tags_resp.json()]
    assert "a-secret-tag" not in b_tag_names, (
        f"User B should not see user A's tag, but got: {b_tag_names}"
    )

    # User B cannot attach a tag to user A's note (403 — ownership)
    b_attach_resp = await user_b_client.post(
        f"/notes/{a_note['id']}/tags", json={"name": "b-hacks-a"}
    )
    assert b_attach_resp.status_code == 403, (
        f"Expected 403 when B tags A's note, got {b_attach_resp.status_code}"
    )
