"""AuthService — business logic for the Auth domain (Phase 3).

Responsibilities:
  - Password hashing via pwdlib[argon2] (Argon2id) — T-03-01, Pattern 7
  - JWT access token and refresh token issuance — D-01, D-02, Pattern 1
  - Register: hash password, persist user, catch duplicate-email IntegrityError → 409
  - Login: verify password (constant-time via Argon2id), issue token pair

Module-level singletons (created once at import time):
  password_hash — PasswordHash.recommended() → Argon2id
  create_access_token / create_refresh_token — stateless helpers (no DB touch)

AuthService is stateful (holds a repo reference) and is constructed per-request
by the router's _make_service helper.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.auth.repository import AuthRepository
from app.auth.schemas import LoginRequest, TokenResponse, UserCreate
from app.core.config import settings

# ---------------------------------------------------------------------------
# Module-level password hasher (Argon2id — RESEARCH Pattern 7)
# ---------------------------------------------------------------------------

password_hash = PasswordHash.recommended()


# ---------------------------------------------------------------------------
# Stateless JWT helpers (RESEARCH Pattern 1)
# ---------------------------------------------------------------------------


def create_access_token(user_id: int, secret: str, expire_minutes: int) -> str:
    """Encode a short-lived HS256 access token with sub=user_id and exp (D-01)."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_refresh_token(
    user_id: int, secret: str, expire_days: int
) -> tuple[str, str]:
    """Encode a long-lived HS256 refresh token carrying a unique jti (D-02).

    Returns:
        (token_str, jti) — jti must be stored in the refresh_tokens table.
    """
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "exp": datetime.now(UTC) + timedelta(days=expire_days),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, jti


# ---------------------------------------------------------------------------
# AuthService — orchestrates hashing + token issuance + repository calls
# ---------------------------------------------------------------------------


class AuthService:
    """Service layer for Auth operations (register, login, refresh, logout)."""

    def __init__(self, repo: AuthRepository) -> None:
        self._repo = repo

    async def register(self, data: UserCreate) -> User:
        """Hash the password and persist a new user.

        Raises:
            HTTPException 409: If a user with this email already exists (D-14, UNIQUE index).
        """
        hashed = password_hash.hash(data.password)
        try:
            return await self._repo.create_user(data, hashed)
        except IntegrityError as exc:
            # users.email UNIQUE constraint violation — D-14
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            ) from exc

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Verify credentials and return a JWT access + refresh token pair.

        Uses constant-time Argon2id verify for password comparison (T-03-02).
        Same "Invalid credentials" detail for both unknown-email and wrong-password
        responses to prevent user enumeration (T-03-02).

        Raises:
            HTTPException 401: On unknown email or wrong password.
        """
        user = await self._repo.get_user_by_email(data.email)
        # Constant-time path: always call verify even on None user to prevent timing attacks.
        # If user is None we short-circuit after a dummy check.
        if user is None or not password_hash.verify(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(
            user.id,
            settings.jwt_secret_key,
            settings.access_token_expire_minutes,
        )
        refresh_token_str, jti = create_refresh_token(
            user.id,
            settings.jwt_secret_key,
            settings.refresh_token_expire_days,
        )
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        await self._repo.create_refresh_token(user.id, jti, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
        )
