"""FastAPI router for Auth endpoints (Phase 3).

Endpoints (all served under the /auth prefix registered in app/main.py):
  POST /auth/register  — create a new user account (returns 201 + UserRead)
  POST /auth/login     — verify credentials and return a JWT token pair (200)

Endpoints scaffolded for Plan 02:
  POST /auth/refresh   — rotate refresh token (Plan 02)
  POST /auth/logout    — revoke refresh token (Plan 02)

Status codes follow REST conventions:
  201 — Created (register)
  200 — OK (login, refresh)
  204 — No Content (logout)
  401 — Unauthorized (bad credentials / invalid token)
  409 — Conflict (duplicate email)
  422 — Validation error (Pydantic)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import AuthRepository
from app.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from app.auth.service import AuthService
from app.core.dependencies import get_db

router = APIRouter(tags=["auth"])


def _make_service(session: AsyncSession) -> AuthService:
    """Construct AuthService with its repository for the current request session."""
    return AuthService(AuthRepository(session))


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Invalid email or weak password"},
    },
)
async def register(
    data: UserCreate,
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    """POST /auth/register — create a new user account.

    Returns 201 + UserRead on success.
    Returns 409 if the email is already taken (D-14).
    Returns 422 if email is malformed (D-12) or password is too weak (D-13).
    """
    user = await _make_service(session).register(data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT token pair",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """POST /auth/login — verify credentials and return an access + refresh token pair.

    Returns 200 + TokenResponse on success (D-01, D-02).
    Returns 401 on invalid email or wrong password.
    """
    return await _make_service(session).login(data)
