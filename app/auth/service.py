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

# Fixed dummy Argon2id hash used to equalise login timing when the email is
# unknown (WR-04). Verifying against this on the no-user path makes the
# unknown-email and wrong-password branches both pay one full Argon2id verify,
# closing the user-enumeration timing oracle.
_DUMMY_PASSWORD_HASH = password_hash.hash("timing-equalizer-not-a-real-password")


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
        invalid_credentials = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        user = await self._repo.get_user_by_email(data.email)
        # Timing-equalised path (WR-04): both the unknown-email and the
        # wrong-password branches perform exactly one Argon2id verify, so an
        # attacker cannot distinguish them by response latency (no user
        # enumeration oracle). `or` would short-circuit and skip the verify on
        # the None-user path, so the unknown-email check is handled explicitly.
        if user is None:
            password_hash.verify(data.password, _DUMMY_PASSWORD_HASH)
            raise invalid_credentials
        if not password_hash.verify(data.password, user.hashed_password):
            raise invalid_credentials

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

    async def rotate_refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """Rotate a refresh token: revoke old jti, issue new access + refresh pair.

        Implements D-04 (rotation) and D-06 (minimal reuse handling: revoked/absent jti → 401,
        no cascade). Only the presented token's jti is rotated — other tokens for the same
        user are unaffected (D-03, T-03-14).

        Args:
            refresh_token_str: The raw JWT string from the client body.

        Returns:
            TokenResponse with a new access_token and a new refresh_token.

        Raises:
            HTTPException 401: On invalid signature, expired token, missing jti,
                or jti already revoked/not found in DB.
        """
        try:
            payload = jwt.decode(
                refresh_token_str,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        jti: str | None = payload.get("jti")
        user_id_str: str | None = payload.get("sub")
        if not jti or user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        invalid_token = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

        # A validly-signed token whose sub is non-numeric must map to 401, not a
        # 500 from an unhandled ValueError (CR-02).
        try:
            user_id = int(user_id_str)
        except (TypeError, ValueError) as exc:
            raise invalid_token from exc

        # DB check — jti must exist, not be revoked, and not be expired
        # (D-06: replay of revoked jti → 401; WR-02: enforce stored expiry as
        # defence-in-depth even if the JWT exp was somehow accepted).
        token_record = await self._repo.get_refresh_token_by_jti(jti)
        now = datetime.now(UTC).replace(tzinfo=None)  # MySQL DATETIME has no tz
        if (
            token_record is None
            or token_record.revoked
            or token_record.expires_at <= now
        ):
            raise invalid_token

        # Atomic, race-safe rotation (WR-01, WR-05):
        #   1. Conditional revoke: UPDATE ... WHERE jti=:jti AND revoked=0.
        #      rowcount==0 means a concurrent refresh already revoked this jti
        #      (replay race) → 401, no new chain issued.
        #   2. Stage the new token in the SAME transaction (no intermediate
        #      commit), then commit once so revoke+insert land atomically. A
        #      crash before commit rolls back both — the old token survives and
        #      the user is not silently logged out.
        revoked_rows = await self._repo.revoke_refresh_token_if_active(jti)
        if revoked_rows == 0:
            raise invalid_token

        new_access = create_access_token(
            user_id,
            settings.jwt_secret_key,
            settings.access_token_expire_minutes,
        )
        new_refresh_str, new_jti = create_refresh_token(
            user_id,
            settings.jwt_secret_key,
            settings.refresh_token_expire_days,
        )
        new_expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        self._repo.add_refresh_token(user_id, new_jti, new_expires_at)
        await self._repo.commit()

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh_str,
        )

    async def logout(self, refresh_token_str: str) -> None:
        """Revoke the given refresh token's jti (D-05).

        A subsequent /auth/refresh with the same token will return 401 (T-03-11).
        No cascade revocation — only this token's jti is revoked (D-06).
        If the token is already revoked or not found, the call is a no-op (idempotent).

        Args:
            refresh_token_str: The raw JWT string from the client body.

        Raises:
            HTTPException 401: If the JWT cannot be decoded (undecodable token).
        """
        try:
            payload = jwt.decode(
                refresh_token_str,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
            # Undecodable token → 401; we cannot look up the jti without a valid payload
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        jti: str | None = payload.get("jti")
        if not jti:
            return  # No jti to revoke — treat as no-op

        token_record = await self._repo.get_refresh_token_by_jti(jti)
        if token_record is not None and not token_record.revoked:
            await self._repo.revoke_refresh_token(token_record)
