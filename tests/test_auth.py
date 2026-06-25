"""Integration tests for the auth domain (Phase 3, Plans 01 and 02).

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

  AUTH-03 — get_current_user dependency (Plan 02, Task 1):
    - Missing credentials (None) → HTTPException 401
    - Invalid/garbage bearer token → HTTPException 401
    - Expired access token → HTTPException 401
    - Valid access token → returns matching User
    - Token for non-existent user → HTTPException 401

  AUTH-03 — refresh rotation and logout (Plan 02, Task 2):
    - POST /auth/refresh returns new access_token + new refresh_token (200)
    - Old refresh token revoked after rotation → 401 on replay
    - New refresh_token from /refresh can be used again → 200
    - Garbage refresh token → 401
    - Expired refresh token → 401
    - POST /auth/logout → 204 (empty body)
    - Refresh after logout → 401 (D-05)
    - Rotating one of two concurrent refresh tokens leaves the other valid (D-03)
"""

from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

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


# ---------------------------------------------------------------------------
# get_current_user dependency unit tests (AUTH-03, Plan 02 Task 1)
# ---------------------------------------------------------------------------


async def test_no_token_returns_401(session: AsyncSession) -> None:
    """get_current_user with credentials=None must raise HTTPException 401 (not 403, Pitfall 3)."""
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    gen = get_current_user(credentials=None, db=session)
    with pytest.raises(HTTPException) as exc_info:
        await gen.__anext__() if hasattr(gen, "__anext__") else await gen
    assert exc_info.value.status_code == 401


async def test_invalid_token_returns_401(session: AsyncSession) -> None:
    """get_current_user with a garbage bearer string must raise HTTPException 401."""
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="garbage.token.here")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=session)
    assert exc_info.value.status_code == 401


async def test_expired_token_returns_401(session: AsyncSession) -> None:
    """get_current_user with an expired access token must raise HTTPException 401."""
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    expired_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=session)
    assert exc_info.value.status_code == 401


async def test_valid_token_returns_user(client: httpx.AsyncClient, session: AsyncSession) -> None:
    """get_current_user with a valid access token must return the matching User."""
    from app.auth.service import create_access_token  # noqa: PLC0415
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    # Register a user to get a real user_id
    reg = await client.post(
        "/auth/register",
        json={"email": "gcuvalid@example.com", "password": "Test1234!"},
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    token = create_access_token(
        user_id,
        settings.jwt_secret_key,
        settings.access_token_expire_minutes,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials=creds, db=session)
    assert user.id == user_id
    assert user.email == "gcuvalid@example.com"


async def test_non_numeric_sub_returns_401(session: AsyncSession) -> None:
    """A validly-signed token with a non-numeric sub must raise 401, not 500 (CR-02)."""
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    bad_sub_token = jwt.encode(
        {
            "sub": "not-an-integer",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad_sub_token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=session)
    assert exc_info.value.status_code == 401


async def test_refresh_non_numeric_sub_returns_401(client: httpx.AsyncClient) -> None:
    """POST /auth/refresh with a non-numeric sub must return 401, not 500 (CR-02)."""
    bad_sub_token = jwt.encode(
        {
            "sub": "not-an-integer",
            "jti": "some-jti",
            "exp": datetime.now(UTC) + timedelta(days=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.post("/auth/refresh", json={"refresh_token": bad_sub_token})
    assert resp.status_code == 401


async def test_token_for_deleted_user_returns_401(session: AsyncSession) -> None:
    """get_current_user with sub pointing to a non-existent user must raise HTTPException 401."""
    from app.auth.service import create_access_token  # noqa: PLC0415
    from app.core.dependencies import get_current_user  # noqa: PLC0415

    # Use a user_id that does not exist
    token = create_access_token(
        999999,
        settings.jwt_secret_key,
        settings.access_token_expire_minutes,
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=creds, db=session)
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Refresh rotation and logout (AUTH-03, Plan 02 Task 2)
# ---------------------------------------------------------------------------


async def test_refresh_rotation(client: httpx.AsyncClient) -> None:
    """POST /auth/refresh returns new access_token + new refresh_token (200, D-04)."""
    email, password = "refresh1@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    old_refresh = login.json()["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["refresh_token"] != old_refresh  # rotation produced a new token


async def test_old_refresh_token_revoked_after_rotation(client: httpx.AsyncClient) -> None:
    """After rotation, replaying the original refresh_token must return 401 (D-04/D-06)."""
    email, password = "refresh2@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})
    login = await client.post("/auth/login", json={"email": email, "password": password})
    old_refresh = login.json()["refresh_token"]

    # Do the rotation
    rotate = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotate.status_code == 200

    # Replay the OLD token — must fail
    replay = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


async def test_new_refresh_token_works_after_rotation(client: httpx.AsyncClient) -> None:
    """The refresh_token returned by /auth/refresh can itself be used for a further rotation."""
    email, password = "refresh3@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})
    login = await client.post("/auth/login", json={"email": email, "password": password})
    old_refresh = login.json()["refresh_token"]

    # First rotation
    rotate1 = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert rotate1.status_code == 200
    new_refresh = rotate1.json()["refresh_token"]

    # Second rotation using the new token — must succeed
    rotate2 = await client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert rotate2.status_code == 200


async def test_refresh_invalid_token_returns_401(client: httpx.AsyncClient) -> None:
    """POST /auth/refresh with a garbage token must return 401."""
    resp = await client.post("/auth/refresh", json={"refresh_token": "garbage.token"})
    assert resp.status_code == 401


async def test_refresh_expired_token_returns_401(client: httpx.AsyncClient) -> None:
    """POST /auth/refresh with an expired refresh JWT must return 401."""
    expired_token = jwt.encode(
        {
            "sub": "1",
            "jti": "test-jti",
            "exp": datetime.now(UTC) - timedelta(days=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.post("/auth/refresh", json={"refresh_token": expired_token})
    assert resp.status_code == 401


async def test_logout_returns_204(client: httpx.AsyncClient) -> None:
    """POST /auth/logout with a valid refresh token must return 204 with empty body."""
    email, password = "logout1@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})
    login = await client.post("/auth/login", json={"email": email, "password": password})
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert resp.status_code == 204
    assert resp.content == b""


async def test_logout_then_refresh_returns_401(client: httpx.AsyncClient) -> None:
    """After logout, POST /auth/refresh with that token must return 401 (D-05)."""
    email, password = "logout2@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})
    login = await client.post("/auth/login", json={"email": email, "password": password})
    refresh_token = login.json()["refresh_token"]

    logout = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout.status_code == 204

    refresh = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


async def test_other_refresh_tokens_unaffected_by_rotation(client: httpx.AsyncClient) -> None:
    """Rotating one refresh token must NOT revoke sibling tokens for the same user (D-03)."""
    email, password = "concurrent@example.com", "Test1234!"
    await client.post("/auth/register", json={"email": email, "password": password})

    # Two independent logins → two independent refresh tokens
    login1 = await client.post("/auth/login", json={"email": email, "password": password})
    login2 = await client.post("/auth/login", json={"email": email, "password": password})
    token1 = login1.json()["refresh_token"]
    token2 = login2.json()["refresh_token"]

    # Rotate token1
    rotate = await client.post("/auth/refresh", json={"refresh_token": token1})
    assert rotate.status_code == 200

    # token2 must still work
    resp = await client.post("/auth/refresh", json={"refresh_token": token2})
    assert resp.status_code == 200
