"""AuthRepository — all SQL for the Auth domain.

Design principles:
- Zero business logic here. No HTTP concerns. Pure data access.
- All queries use SQLAlchemy 2.x select() + scalars() async pattern.
- Session injected via constructor for easy testing.

Methods:
  create_user              — INSERT users row (receives already-hashed password)
  get_user_by_id           — SELECT by PK
  get_user_by_email        — SELECT by email (unique)
  create_refresh_token     — INSERT refresh_tokens row
  get_refresh_token_by_jti — SELECT by jti (for Plan 02 rotation / revocation check)
  revoke_refresh_token     — UPDATE revoked=True, revoked_at=now (Plan 02)
"""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.auth.schemas import UserCreate


class AuthRepository:
    """Data-access layer for User and RefreshToken records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Commit the current transaction.

        Exposed so the service can own the transaction boundary for multi-step
        operations (e.g. atomic refresh rotation: revoke + insert in one commit).
        """
        await self._session.commit()

    async def create_user(self, data: UserCreate, hashed_password: str) -> User:
        """Insert a new User row and return the persisted model instance.

        Hashing must happen in the service layer — this method receives the hash.
        Raises sqlalchemy.exc.IntegrityError on duplicate email (caught in service).
        """
        user = User(
            email=data.email,
            hashed_password=hashed_password,
        )
        self._session.add(user)
        await self._session.commit()
        await self._session.refresh(user)
        return user

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return the User with the given id, or None if not found."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Return the User with the given email, or None if not found."""
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_refresh_token(
        self,
        user_id: int,
        jti: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Insert a new RefreshToken row and return the persisted instance."""
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.commit()
        await self._session.refresh(token)
        return token

    def add_refresh_token(
        self,
        user_id: int,
        jti: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Stage a new RefreshToken in the session WITHOUT committing.

        Used by the atomic rotation path (WR-01): the service revokes the old
        jti and inserts the new one inside a single transaction, then commits
        once. The transaction boundary is owned by the service, not the repo.
        """
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
        )
        self._session.add(token)
        return token

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        """Return the RefreshToken row with the given jti, or None."""
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        """Mark a refresh token as revoked (D-05 — used by Plan 02 logout)."""
        token.revoked = True
        token.revoked_at = datetime.now(UTC).replace(tzinfo=None)  # MySQL DATETIME has no tz
        await self._session.commit()
        await self._session.refresh(token)

    async def revoke_refresh_token_if_active(self, jti: str) -> int:
        """Conditionally revoke a token in a single atomic SQL UPDATE.

        Issues `UPDATE refresh_tokens SET revoked=1, revoked_at=now
        WHERE jti=:jti AND revoked=0`. The WHERE clause makes the revoke
        race-safe: two concurrent /auth/refresh calls presenting the same jti
        cannot both win — the DB serialises the row update, so exactly one sees
        rowcount==1 and the loser sees rowcount==0 (WR-05).

        This does NOT commit — the caller (service) owns the transaction so the
        revoke and the new-token insert land atomically (WR-01).

        Returns:
            The number of rows updated: 1 if this call performed the revoke,
            0 if the token was already revoked / does not exist.
        """
        result = await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked.is_(False))
            .values(
                revoked=True,
                revoked_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        # session.execute() is typed as returning Result, but an UPDATE yields a
        # CursorResult which carries rowcount.
        return cast(CursorResult, result).rowcount
