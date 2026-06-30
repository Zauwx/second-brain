"""Integration tests for GET /notes/ tag filtering — ORG-02 coverage.

Tests verify AND-intersection tag filtering on the note list endpoint:
  - Single tag filter: GET /notes/?tag=python returns only python-tagged notes
  - Multi-tag AND filter: GET /notes/?tag=python&tag=docker returns notes with BOTH
  - Normalization: ?tag=Python matches a note stored with tag "python"
  - Items include tags: filtered results carry a populated tags array (no N+1)

All tests run against real MySQL via conftest.py testcontainer fixtures.
These tests are written BEFORE the implementation exists (TDD RED phase).

asyncio_mode="auto" is set in pyproject.toml — no @pytest.mark.asyncio needed.
"""

import httpx


async def _attach(client: httpx.AsyncClient, note_id: int, tag_name: str) -> None:
    """Attach `tag_name` to note `note_id`; assert 200."""
    resp = await client.post(f"/notes/{note_id}/tags", json={"name": tag_name})
    assert resp.status_code == 200, f"Expected 200 on attach, got {resp.status_code}"


async def test_single_tag_filter(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?tag=python returns the python-tagged note and excludes others."""
    n1 = (await auth_client.post("/notes/", json={"content": "python note"})).json()
    n2 = (await auth_client.post("/notes/", json={"content": "docker note"})).json()
    assert "id" in n1 and "id" in n2

    await _attach(auth_client, n1["id"], "python")

    resp = await auth_client.get("/notes/?tag=python")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert n1["id"] in ids, f"Expected python note {n1['id']} in results, got {ids}"
    assert n2["id"] not in ids, f"Untagged note {n2['id']} should not appear, got {ids}"


async def test_multi_tag_and_filter(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?tag=python&tag=docker returns only the note with BOTH tags.

    A note with only "python" must NOT appear (strict AND, not OR).
    """
    n_both = (await auth_client.post("/notes/", json={"content": "both tags note"})).json()
    n_one = (await auth_client.post("/notes/", json={"content": "python-only note"})).json()
    assert "id" in n_both and "id" in n_one

    await _attach(auth_client, n_both["id"], "python")
    await _attach(auth_client, n_both["id"], "docker")
    await _attach(auth_client, n_one["id"], "python")

    resp = await auth_client.get("/notes/?tag=python&tag=docker")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert n_both["id"] in ids, (
        f"Note with both tags should be included, got ids: {ids}"
    )
    assert n_one["id"] not in ids, (
        f"Python-only note {n_one['id']} should NOT appear when filtering python+docker, got {ids}"
    )


async def test_tag_filter_normalization(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?tag=Python (uppercase) matches a note stored with tag 'python'."""
    note = (await auth_client.post("/notes/", json={"content": "normalization test note"})).json()
    assert "id" in note

    await _attach(auth_client, note["id"], "python")

    resp = await auth_client.get("/notes/?tag=Python")
    assert resp.status_code == 200

    ids = [item["id"] for item in resp.json()["items"]]
    assert note["id"] in ids, (
        f"Expected note tagged 'python' to match '?tag=Python', got ids: {ids}"
    )


async def test_filtered_items_include_tags(auth_client: httpx.AsyncClient) -> None:
    """Filtered results include a non-empty tags array on each matching item."""
    note = (await auth_client.post("/notes/", json={"content": "tagged item test"})).json()
    assert "id" in note

    await _attach(auth_client, note["id"], "fastapi")

    resp = await auth_client.get("/notes/?tag=fastapi")
    assert resp.status_code == 200

    items = resp.json()["items"]
    assert len(items) >= 1, "Expected at least one result for tag filter"

    matching = next((i for i in items if i["id"] == note["id"]), None)
    assert matching is not None, f"Note {note['id']} not found in filtered items"

    tags = matching.get("tags", [])
    assert isinstance(tags, list), "tags field must be a list"
    assert len(tags) >= 1, "Filtered item must include its tags (selectinload, no N+1)"
    tag_names = [t["name"] for t in tags]
    assert "fastapi" in tag_names, (
        f"Expected 'fastapi' in tags of filtered result, got: {tag_names}"
    )
