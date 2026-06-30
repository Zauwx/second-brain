"""Consolidated cross-user isolation proof for Phase 4 (success criterion 5).

This is the single authoritative end-to-end isolation gate spanning tags, collections,
search, and tag-filter — proving that user A can never read or modify user B's resources
and that search/tag-filter never leak data across users (T-04-iso).

Deliberately overlaps the per-slice isolation tests (test_tag_isolation,
test_collection_isolation, test_search_isolation) as the consolidated gate for
success criterion 5.  Each per-slice plan asserts its own isolation; this plan is
the binding, exhaustive proof across ALL three Phase-4 resources.

Resources under test:
  - Tags: GET /tags, DELETE /notes/{id}/tags/{name}
  - Collections: GET /collections/, GET /collections/{id}/notes,
                 POST /collections/{id}/notes
  - Search: GET /search/?q=
  - Tag filter: GET /notes/?tag=

Ownership contract (Phase 3, D-08):
  - 403 if the resource exists but is owned by another user
  - 404 if the resource does not exist

Uses `user_a_client` and `user_b_client` AsyncClient fixtures from conftest.py —
two independently authenticated AsyncClients that share the per-test rollback
transaction.  All tests run against real MySQL via testcontainers (D-16).
"""

import httpx


# ---------------------------------------------------------------------------
# Tag isolation
# ---------------------------------------------------------------------------


async def test_tag_list_does_not_leak_across_users(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B's GET /tags never returns a tag created by user A.

    Verifies T-04-02: GET /tags is scoped strictly to the caller's user_id.
    """
    # User A creates a note and attaches a private tag
    a_note = (
        await user_a_client.post("/notes/", json={"content": "A's private tagged note"})
    ).json()
    assert "id" in a_note

    tag_resp = await user_a_client.post(
        f"/notes/{a_note['id']}/tags", json={"name": "a-secret-phase4"}
    )
    assert tag_resp.status_code == 200

    # User B's tag list must NOT include A's tag
    b_tags_resp = await user_b_client.get("/tags")
    assert b_tags_resp.status_code == 200
    b_tag_names = [t["name"] for t in b_tags_resp.json()]
    assert "a-secret-phase4" not in b_tag_names, (
        f"User B must not see user A's tag; got: {b_tag_names}"
    )


async def test_tag_detach_on_other_users_note_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B cannot detach a tag from user A's note — must return 403 Forbidden.

    Verifies T-04-iso: TagService.get_or_404_owned raises HTTP 403 for a note
    whose user_id does not match the caller.
    """
    # User A creates a note and attaches a tag
    a_note = (
        await user_a_client.post("/notes/", json={"content": "A's note to protect"})
    ).json()
    assert "id" in a_note

    tag_resp = await user_a_client.post(
        f"/notes/{a_note['id']}/tags", json={"name": "do-not-touch"}
    )
    assert tag_resp.status_code == 200

    # User B attempts to detach A's tag — must get 403
    del_resp = await user_b_client.delete(
        f"/notes/{a_note['id']}/tags/do-not-touch"
    )
    assert del_resp.status_code == 403, (
        f"Expected 403 when B detaches A's tag, got {del_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Collection isolation
# ---------------------------------------------------------------------------


async def test_collection_list_does_not_leak_across_users(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """User B's GET /collections/ never lists user A's collections.

    Verifies T-04-06: list_by_user is scoped to the caller; B's listing excludes
    every collection created by A.
    """
    # User A creates a collection
    coll_resp = await user_a_client.post(
        "/collections/", json={"name": "A's Confidential Collection"}
    )
    assert coll_resp.status_code == 201
    a_coll_id = coll_resp.json()["id"]

    # User B's collection list must NOT contain A's collection
    b_resp = await user_b_client.get("/collections/")
    assert b_resp.status_code == 200
    b_ids = [c["id"] for c in b_resp.json()]
    assert a_coll_id not in b_ids, (
        f"User B must not see user A's collection (id={a_coll_id}); B has: {b_ids}"
    )


async def test_collection_notes_on_other_users_collection_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """GET /collections/{id}/notes on another user's collection returns 403.

    Verifies T-04-iso: CollectionService.get_or_404_owned raises HTTP 403 for
    collections owned by a different user.
    """
    # User A creates a collection and adds a note
    coll_resp = await user_a_client.post("/collections/", json={"name": "A's Private List"})
    assert coll_resp.status_code == 201
    coll_id = coll_resp.json()["id"]

    note_resp = await user_a_client.post("/notes/", json={"content": "A's private note"})
    assert note_resp.status_code == 201
    note_id = note_resp.json()["id"]

    add_resp = await user_a_client.post(
        f"/collections/{coll_id}/notes", json={"note_id": note_id}
    )
    assert add_resp.status_code == 204

    # User B tries to list A's collection notes → 403
    list_resp = await user_b_client.get(f"/collections/{coll_id}/notes")
    assert list_resp.status_code == 403, (
        f"Expected 403 when B reads A's collection notes, got {list_resp.status_code}"
    )


async def test_add_note_to_other_users_collection_returns_403(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """POST /collections/{id}/notes to another user's collection returns 403.

    Verifies T-04-iso: B cannot inject notes into A's collection; the service
    checks collection ownership before allowing the add.
    """
    # User A creates a collection
    coll_resp = await user_a_client.post(
        "/collections/", json={"name": "A's Locked Collection"}
    )
    assert coll_resp.status_code == 201
    a_coll_id = coll_resp.json()["id"]

    # User B creates their own note then tries to add it to A's collection
    b_note = (
        await user_b_client.post("/notes/", json={"content": "B's note to inject"})
    ).json()

    add_resp = await user_b_client.post(
        f"/collections/{a_coll_id}/notes", json={"note_id": b_note["id"]}
    )
    assert add_resp.status_code == 403, (
        f"Expected 403 when B adds note to A's collection, got {add_resp.status_code}"
    )


async def test_missing_collection_returns_404(
    user_b_client: httpx.AsyncClient,
) -> None:
    """GET /collections/999999/notes on a non-existent collection returns 404.

    Verifies the 404-vs-403 ownership contract: a resource that does not exist
    returns 404 regardless of the caller's identity.
    """
    resp = await user_b_client.get("/collections/999999/notes")
    assert resp.status_code == 404, (
        f"Expected 404 for missing collection, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Search isolation (T-04-iso)
# ---------------------------------------------------------------------------


async def test_search_does_not_leak_across_users(
    ft_user_a_client: httpx.AsyncClient,
    ft_user_b_client: httpx.AsyncClient,
) -> None:
    """GET /search/?q= never returns another user's notes — total must be 0.

    Verifies T-04-iso: SearchRepository.search_fulltext applies
    `WHERE Note.user_id == caller.id` so user B's results are always scoped
    to B's own notes only.

    WR-03: this runs on COMMITTED sessions so InnoDB's FULLTEXT index actually
    indexes A's note. The positive control (A finds the term) proves the row is
    indexed; B's total == 0 then genuinely exercises the user_id scoping clause —
    it is no longer trivially true because of an unindexed row.
    """
    unique_term = "xph4isolationgate2026"
    r = await ft_user_a_client.post(
        "/notes/",
        json={"content": f"A's private content containing {unique_term}"},
    )
    assert r.status_code == 201

    # Positive control: A CAN find their own committed (indexed) note.
    a_resp = await ft_user_a_client.get("/search/", params={"q": unique_term})
    assert a_resp.status_code == 200
    assert a_resp.json()["total"] >= 1, (
        "A's own committed note must be FULLTEXT-indexed and findable — "
        "otherwise B's total == 0 below would be trivially true"
    )

    # User B searches for A's unique term — must get total == 0 (user_id scoping)
    resp = await ft_user_b_client.get("/search/", params={"q": unique_term})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0, (
        f"User B must not find user A's content; got total={data['total']}, "
        f"items={data['items']}"
    )
    assert data["items"] == []


# ---------------------------------------------------------------------------
# Tag-filter isolation (T-04-iso, T-04-04)
# ---------------------------------------------------------------------------


async def test_tag_filter_does_not_leak_across_users(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """GET /notes/?tag= never returns another user's notes.

    Verifies T-04-iso: the tag-filter subquery in NoteRepository.list_paginated
    scopes BOTH the tag lookup (Tag.user_id == caller.id) AND the note result
    (Note.user_id == caller.id), making cross-user tag leakage impossible.
    """
    # User A creates a note and attaches a unique private tag
    a_note = (
        await user_a_client.post("/notes/", json={"content": "A's note with private tag"})
    ).json()
    assert "id" in a_note

    tag_resp = await user_a_client.post(
        f"/notes/{a_note['id']}/tags", json={"name": "only-user-a-has-this-tag"}
    )
    assert tag_resp.status_code == 200

    # User B filters notes by A's private tag name — must get empty results
    b_filter_resp = await user_b_client.get(
        "/notes/", params={"tag": "only-user-a-has-this-tag"}
    )
    assert b_filter_resp.status_code == 200
    data = b_filter_resp.json()
    assert data["total"] == 0, (
        f"User B must not see user A's tagged notes; got total={data['total']}"
    )
    assert data["items"] == []
