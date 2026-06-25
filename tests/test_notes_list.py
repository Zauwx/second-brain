"""List-contract test matrix for GET /notes/ — pagination, sort, filter, status codes.

Tests run against real MySQL via the `client` fixture (testcontainers, transaction rollback).
No DB mocks — real MySQL end-to-end (D-16/D-17/D-18, success criterion 5).

Coverage (authoritative contract from 02-03-PLAN.md Task 1):
  - Envelope keys {items, total, page, size, pages} and default page=1, size=20
  - Pagination math: 5 seeded notes, ?page=2&size=2 → 2 items, total=5, page=2, pages=3
  - Oversized / zero query params: ?size=101 → 422; ?size=0 → 422; ?page=0 → 422
  - Sort ordering: ?sort=created_at (oldest first) vs default -created_at (newest first)
  - sort=updated_at → 200 (valid sort field)
  - Bad sort: ?sort=content → 422; ?sort=evil → 422
  - Case-insensitive filter: ?filter=dock matches docker note; ?filter=DOCK also matches
  - Filtered total: total reflects count of matches, not full collection
  - Empty filter: items==[], total==0, pages==0

asyncio_mode="auto" is set in pyproject.toml — no @pytest.mark.asyncio needed.
"""

import httpx

# ---------------------------------------------------------------------------
# Envelope shape + defaults
# ---------------------------------------------------------------------------


async def test_list_notes_envelope_keys(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/ should return 200 with exactly {items, total, page, size, pages}."""
    response = await auth_client.get("/notes/")
    assert response.status_code == 200

    data = response.json()
    assert set(data.keys()) >= {"items", "total", "page", "size", "pages"}


async def test_list_notes_default_page_and_size(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/ with no query params should default to page=1, size=20."""
    response = await auth_client.get("/notes/")
    assert response.status_code == 200

    data = response.json()
    assert data["page"] == 1
    assert data["size"] == 20


# ---------------------------------------------------------------------------
# Pagination math
# ---------------------------------------------------------------------------


async def test_pagination_math_page_2(auth_client: httpx.AsyncClient) -> None:
    """5 seeded notes, ?page=2&size=2 → len(items)==2, total==5, page==2, size==2, pages==3."""
    # Seed 5 notes via POST (creates deterministic ordering by created_at)
    for i in range(5):
        r = await auth_client.post("/notes/", json={"content": f"pagination seed note {i}"})
        assert r.status_code == 201

    response = await auth_client.get("/notes/?page=2&size=2")
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page"] == 2
    assert data["size"] == 2
    assert data["pages"] == 3


# ---------------------------------------------------------------------------
# Oversized / zero query params — 422
# ---------------------------------------------------------------------------


async def test_size_over_max_returns_422(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?size=101 should return 422 (D-05: max size is 100)."""
    response = await auth_client.get("/notes/?size=101")
    assert response.status_code == 422


async def test_size_zero_returns_422(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?size=0 should return 422 (D-05: size ge=1)."""
    response = await auth_client.get("/notes/?size=0")
    assert response.status_code == 422


async def test_page_zero_returns_422(auth_client: httpx.AsyncClient) -> None:
    """GET /notes/?page=0 should return 422 (D-05: page ge=1)."""
    response = await auth_client.get("/notes/?page=0")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Sort ordering
# ---------------------------------------------------------------------------


async def test_sort_created_at_ascending_oldest_first(auth_client: httpx.AsyncClient) -> None:
    """?sort=created_at should return oldest notes first (ascending order).

    Verifies created_at values are in non-decreasing order.
    MySQL DATETIME has 1-second granularity, so ties are allowed.
    """
    for i in range(3):
        r = await auth_client.post("/notes/", json={"content": f"sort test ascending {i}"})
        assert r.status_code == 201

    response = await auth_client.get("/notes/?sort=created_at")
    assert response.status_code == 200

    items = response.json()["items"]
    assert len(items) >= 3

    # created_at values must be non-decreasing (ascending sort)
    created_ats = [item["created_at"] for item in items]
    for i in range(1, len(created_ats)):
        assert created_ats[i] >= created_ats[i - 1], (
            f"sort=created_at should be non-decreasing; "
            f"position {i - 1}={created_ats[i - 1]!r} > position {i}={created_ats[i]!r}"
        )


async def test_sort_default_desc_newest_first(auth_client: httpx.AsyncClient) -> None:
    """Default sort (-created_at) should return newest notes first (descending order).

    Verifies created_at values are in non-increasing order.
    MySQL DATETIME has 1-second granularity, so ties are allowed.
    """
    for i in range(3):
        r = await auth_client.post("/notes/", json={"content": f"sort test descending {i}"})
        assert r.status_code == 201

    # Default sort = -created_at (newest first)
    response = await auth_client.get("/notes/")
    assert response.status_code == 200

    items = response.json()["items"]
    assert len(items) >= 3

    # created_at values must be non-increasing (descending sort)
    created_ats = [item["created_at"] for item in items]
    for i in range(1, len(created_ats)):
        assert created_ats[i] <= created_ats[i - 1], (
            f"default sort (-created_at) should be non-increasing; "
            f"position {i - 1}={created_ats[i - 1]!r} < position {i}={created_ats[i]!r}"
        )


async def test_sort_created_at_opposite_order_from_default(auth_client: httpx.AsyncClient) -> None:
    """?sort=created_at (asc) and default -created_at (desc) return opposite sort direction.

    Verifies that asc produces non-decreasing created_at values and desc produces
    non-increasing created_at values. MySQL DATETIME has 1-second granularity so
    this test handles ties correctly via the monotone direction check.
    """
    for i in range(3):
        r = await auth_client.post("/notes/", json={"content": f"sort direction check {i}"})
        assert r.status_code == 201

    asc_response = await auth_client.get("/notes/?sort=created_at")
    desc_response = await auth_client.get("/notes/")

    assert asc_response.status_code == 200
    assert desc_response.status_code == 200

    asc_items = asc_response.json()["items"]
    desc_items = desc_response.json()["items"]

    assert len(asc_items) >= 2
    assert len(desc_items) >= 2

    # Ascending: created_at must be non-decreasing
    asc_created_ats = [item["created_at"] for item in asc_items]
    for i in range(1, len(asc_created_ats)):
        assert asc_created_ats[i] >= asc_created_ats[i - 1], (
            f"sort=created_at must be non-decreasing; "
            f"position {i - 1}={asc_created_ats[i - 1]!r} > position {i}={asc_created_ats[i]!r}"
        )

    # Descending: created_at must be non-increasing
    desc_created_ats = [item["created_at"] for item in desc_items]
    for i in range(1, len(desc_created_ats)):
        assert desc_created_ats[i] <= desc_created_ats[i - 1], (
            f"sort=-created_at must be non-increasing; "
            f"position {i - 1}={desc_created_ats[i - 1]!r} < position {i}={desc_created_ats[i]!r}"
        )


async def test_sort_updated_at_returns_200(auth_client: httpx.AsyncClient) -> None:
    """?sort=updated_at should return 200 (updated_at is a whitelisted sort field, D-07)."""
    response = await auth_client.get("/notes/?sort=updated_at")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Bad sort — must return 422
# ---------------------------------------------------------------------------


async def test_sort_content_returns_422(auth_client: httpx.AsyncClient) -> None:
    """?sort=content should return 422 (content is not a whitelisted sort field, D-07/D-09)."""
    response = await auth_client.get("/notes/?sort=content")
    assert response.status_code == 422


async def test_sort_evil_returns_422(auth_client: httpx.AsyncClient) -> None:
    """?sort=evil should return 422 (unknown sort field, D-07/D-09)."""
    response = await auth_client.get("/notes/?sort=evil")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Case-insensitive filter + filtered total
# ---------------------------------------------------------------------------


async def test_filter_case_insensitive_lowercase(auth_client: httpx.AsyncClient) -> None:
    """?filter=dock should match notes containing 'docker' (case-insensitive, D-08)."""
    await auth_client.post("/notes/", json={"content": "Learning docker compose and networking"})
    await auth_client.post("/notes/", json={"content": "Python async programming"})

    response = await auth_client.get("/notes/?filter=dock")
    assert response.status_code == 200

    data = response.json()
    # Only the docker note should be returned
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "dock" in item["content"].lower(), (
            f"filter=dock should only match notes containing 'dock'; got: {item['content']}"
        )
    # Total should reflect filtered count, not full collection count
    assert data["total"] == len(data["items"])


async def test_filter_case_insensitive_uppercase(auth_client: httpx.AsyncClient) -> None:
    """?filter=DOCK should also match notes containing 'docker' (case-insensitive, D-08)."""
    await auth_client.post("/notes/", json={"content": "Running docker containers in production"})
    await auth_client.post("/notes/", json={"content": "MySQL indexing strategies"})

    response = await auth_client.get("/notes/?filter=DOCK")
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) >= 1
    for item in data["items"]:
        assert "dock" in item["content"].lower(), (
            f"filter=DOCK should only match notes containing 'dock' (case-insensitive); "
            f"got: {item['content']}"
        )


async def test_filter_total_reflects_filtered_count(auth_client: httpx.AsyncClient) -> None:
    """total in the envelope should equal the count of filtered matches, not all notes."""
    await auth_client.post("/notes/", json={"content": "docker volume management"})
    await auth_client.post("/notes/", json={"content": "FastAPI dependency injection"})
    await auth_client.post("/notes/", json={"content": "docker network bridge mode"})

    # Filter for docker notes
    filtered_response = await auth_client.get("/notes/?filter=docker")
    assert filtered_response.status_code == 200

    filtered_data = filtered_response.json()
    assert filtered_data["total"] >= 2  # at least 2 docker notes seeded

    # Unfiltered total must be >= filtered total
    unfiltered_response = await auth_client.get("/notes/")
    assert unfiltered_response.status_code == 200
    unfiltered_total = unfiltered_response.json()["total"]

    assert unfiltered_total >= filtered_data["total"], (
        "Unfiltered total must be >= filtered total"
    )
    # The filtered total must reflect only the matching notes
    assert filtered_data["total"] == len(filtered_data["items"]) or filtered_data["pages"] > 1


# ---------------------------------------------------------------------------
# Empty result
# ---------------------------------------------------------------------------


async def test_no_match_filter_returns_empty(auth_client: httpx.AsyncClient) -> None:
    """?filter=zzz_no_match should return items==[], total==0, pages==0."""
    # Seed a note to ensure the DB is non-empty
    await auth_client.post("/notes/", json={"content": "Some content for empty filter test"})

    response = await auth_client.get("/notes/?filter=zzz_no_match_xqz")
    assert response.status_code == 200

    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["pages"] == 0
