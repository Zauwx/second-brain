"""FULLTEXT BOOLEAN MODE search tests (SRCH-01).

Tests verify the GET /search/?q= endpoint behavior:
  - Basic search: notes containing a keyword are returned in NoteListResponse envelope
  - 2-char token search: short tokens like "AI" are searchable (innodb_ft_min_token_size=2)
  - User isolation: search never returns another user's notes (T-04-iso)
  - Boolean operators: +word -word combinations return 200 without crashing
  - Sanitization: malformed operator strings (@@++, stray +) return 200, not 500
  - Whitespace-only q returns empty NoteListResponse (not 500)
  - Unauthenticated request returns 401

asyncio_mode="auto" is set in pyproject.toml — no @pytest.mark.asyncio needed.
"""

import httpx

# ---------------------------------------------------------------------------
# Basic keyword search
# ---------------------------------------------------------------------------


async def test_basic_search_returns_matching_notes(
    ft_auth_client: httpx.AsyncClient,
) -> None:
    """GET /search/?q=python returns notes containing 'python'.

    Uses ft_auth_client (committed session) — InnoDB FULLTEXT only sees committed data.
    """
    r = await ft_auth_client.post(
        "/notes/", json={"content": "Learning python programming with FastAPI"}
    )
    assert r.status_code == 201

    response = await ft_auth_client.get("/search/", params={"q": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # At least one item contains the search term (case-insensitive)
    assert any(
        "python" in (item.get("content") or "").lower() for item in data["items"]
    )


async def test_search_returns_canonical_envelope(
    auth_client: httpx.AsyncClient,
) -> None:
    """GET /search/?q=... returns the canonical NoteListResponse envelope keys."""
    await auth_client.post(
        "/notes/", json={"content": "Testing the search response envelope"}
    )
    response = await auth_client.get("/search/", params={"q": "envelope"})
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"items", "total", "page", "size", "pages"}
    assert data["page"] == 1
    assert data["size"] == 20


# ---------------------------------------------------------------------------
# 2-char token (innodb_ft_min_token_size=2) — D-11
# ---------------------------------------------------------------------------


async def test_two_char_token_search(ft_auth_client: httpx.AsyncClient) -> None:
    """2-char token 'AI' is searchable when innodb_ft_min_token_size=2 (D-11).

    Uses ft_auth_client (committed session) — InnoDB FULLTEXT only sees committed data.
    This test proves the MySQL server was started with --innodb-ft-min-token-size=2
    (set in the testcontainers fixture by Plan 01 and in docker-compose.yml by this plan).
    """
    r = await ft_auth_client.post(
        "/notes/", json={"content": "Exploring AI tools for productivity and automation"}
    )
    assert r.status_code == 201

    response = await ft_auth_client.get("/search/", params={"q": "AI"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


# ---------------------------------------------------------------------------
# User isolation (T-04-iso)
# ---------------------------------------------------------------------------


async def test_search_isolation(
    user_a_client: httpx.AsyncClient,
    user_b_client: httpx.AsyncClient,
) -> None:
    """Search never returns another user's notes — user B cannot find user A's content."""
    # User A creates a note with a rare keyword
    r = await user_a_client.post(
        "/notes/", json={"content": "private xk9qlm2 secret content for isolation test"}
    )
    assert r.status_code == 201

    # User B searches for the same keyword — must return total == 0
    response = await user_b_client.get("/search/", params={"q": "xk9qlm2"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


# ---------------------------------------------------------------------------
# BOOLEAN MODE operators
# ---------------------------------------------------------------------------


async def test_boolean_operators_return_200(auth_client: httpx.AsyncClient) -> None:
    """BOOLEAN MODE +required -excluded operators return 200 without crashing."""
    response = await auth_client.get("/search/", params={"q": "+python -docker"})
    assert response.status_code == 200


async def test_wildcard_operator_returns_200(auth_client: httpx.AsyncClient) -> None:
    """Wildcard suffix operator (word*) returns 200."""
    response = await auth_client.get("/search/", params={"q": "python*"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Input sanitization (T-04-inj, T-04-08)
# ---------------------------------------------------------------------------


async def test_stray_at_operator_returns_200(auth_client: httpx.AsyncClient) -> None:
    """@@ (reserved @distance proximity operator) is sanitized — returns 200, not 500."""
    response = await auth_client.get("/search/", params={"q": "@@test"})
    assert response.status_code == 200


async def test_consecutive_plus_operators_returns_200(
    auth_client: httpx.AsyncClient,
) -> None:
    """Consecutive ++ operators are sanitized — returns 200, not 500."""
    response = await auth_client.get("/search/", params={"q": "++word"})
    assert response.status_code == 200


async def test_mixed_stray_operators_returns_200(
    auth_client: httpx.AsyncClient,
) -> None:
    """@@++ (multiple stray operators) are sanitized — returns 200, not 500."""
    response = await auth_client.get("/search/", params={"q": "@@++"})
    assert response.status_code == 200


async def test_whitespace_only_query_returns_empty_envelope(
    auth_client: httpx.AsyncClient,
) -> None:
    """Whitespace-only q sanitizes to empty — returns empty NoteListResponse (not 500)."""
    response = await auth_client.get("/search/", params={"q": "   "})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["pages"] == 0


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_search_requires_auth(client: httpx.AsyncClient) -> None:
    """GET /search/ without auth token returns 401 (T-04-09)."""
    response = await client.get("/search/", params={"q": "test"})
    assert response.status_code == 401
