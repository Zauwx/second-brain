"""Integration tests for the auth domain (Phase 3, Plan 01).

Coverage:
  AUTH-01 — register endpoint:
    - 201 on valid registration; body has id, email, created_at; NO password/hashed_password
    - 409 on duplicate email
    - 422 on malformed email (D-12)
    - 422 on weak password (D-13)

  AUTH-02 — login endpoint:
    - 200 with access_token + refresh_token + token_type="bearer"
    - 401 on wrong password
    - 401 on unknown email

  Token content (D-01):
    - Access token decodes with correct sub=user_id; contains exp
"""

import jwt
import httpx
import pytest

from app.core.config import settings


# ---------------------------------------------------------------------------
# Register tests (AUTH-01)
# ---------------------------------------------------------------------------


async def test_register_returns_201(client: httpx.AsyncClient) -> None:
    """POST /auth/register with valid body should return 201 + user id/email/created_at."""
    response = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "Test1234!"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert isinstance(body["id"], int)
    assert body["email"] == "new@example.com"
    assert "created_at" in body
    # Ensure hashed_password is NOT in the response (T-03-01)
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_returns_409(client: httpx.AsyncClient) -> None:
    """Registering the same email twice should return 409 on the second call (D-14)."""
    payload = {"email": "dup@example.com", "password": "Test1234!"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already registered"


async def test_register_invalid_email_returns_422(client: httpx.AsyncClient) -> None:
    """POST /auth/register with a malformed email should return 422 (D-12)."""
    response = await client.post(
        "/auth/register",
        json={"email": "notanemail", "password": "Test1234!"},
    )
    assert response.status_code == 422


async def test_register_weak_password_too_short_returns_422(client: httpx.AsyncClient) -> None:
    """Password shorter than 8 characters should return 422 (D-13)."""
    response = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "Short1!"},
    )
    assert response.status_code == 422


async def test_register_weak_password_no_uppercase_returns_422(client: httpx.AsyncClient) -> None:
    """Password missing uppercase letter should return 422 (D-13)."""
    response = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "alllower1!"},
    )
    assert response.status_code == 422


async def test_register_weak_password_no_digit_returns_422(client: httpx.AsyncClient) -> None:
    """Password missing digit should return 422 (D-13)."""
    response = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "NoDigitHere!"},
    )
    assert response.status_code == 422


async def test_register_weak_password_no_symbol_returns_422(client: httpx.AsyncClient) -> None:
    """Password missing symbol should return 422 (D-13)."""
    response = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "NoSymbol1"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login tests (AUTH-02)
# ---------------------------------------------------------------------------


async def test_login_returns_tokens(client: httpx.AsyncClient) -> None:
    """POST /auth/login with valid credentials should return 200 + token pair (AUTH-02)."""
    email, password = "login@example.com", "Test1234!"
    reg = await client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201

    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert isinstance(body["refresh_token"], str)


async def test_login_wrong_password_returns_401(client: httpx.AsyncClient) -> None:
    """Login with wrong password should return 401."""
    email = "wrongpw@example.com"
    await client.post("/auth/register", json={"email": email, "password": "Test1234!"})

    response = await client.post(
        "/auth/login", json={"email": email, "password": "WrongPass9!"}
    )
    assert response.status_code == 401


async def test_login_unknown_email_returns_401(client: httpx.AsyncClient) -> None:
    """Login with never-registered email should return 401."""
    response = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "Test1234!"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Token content test (D-01)
# ---------------------------------------------------------------------------


async def test_access_token_decodes_with_sub(client: httpx.AsyncClient) -> None:
    """Access token payload must contain sub=user_id (str) and exp (D-01)."""
    email, password = "decode@example.com", "Test1234!"
    reg = await client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = await client.post("/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]

    payload = jwt.decode(
        access_token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert payload["sub"] == str(user_id)
    assert "exp" in payload


@pytest.mark.skip(reason="Plan 02 — refresh endpoint not yet implemented")
async def test_refresh_rotation(client: httpx.AsyncClient) -> None:
    """POST /auth/refresh should issue a new token pair and revoke the old jti (D-04)."""
    pass


@pytest.mark.skip(reason="Plan 02 — logout endpoint not yet implemented")
async def test_logout_revokes_token(client: httpx.AsyncClient) -> None:
    """POST /auth/logout should revoke the refresh token jti (D-05)."""
    pass
