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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, User
from app.auth.schemas import UserCreate


class AuthRepository:
    """Data-access layer for User and RefreshToken records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        """Return the RefreshToken row with the given jti, or None."""
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, token: RefreshToken) -> None:
        """Mark a refresh token as revoked (D-05 — used by Plan 02 logout/rotation)."""
        token.revoked = True
        token.revoked_at = datetime.now(UTC).replace(tzinfo=None)  # MySQL DATETIME has no tz
        await self._session.commit()
        await self._session.refresh(token)
