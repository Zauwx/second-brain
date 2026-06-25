"""SQLAlchemy ORM models for the Auth domain (Phase 3).

Models:
  User          — authentication identity; owns Note records.
  RefreshToken  — persisted jti values for refresh token revocation (D-02, D-05).

Table conventions match app/notes/models.py:
  - INTEGER(unsigned=True) PK with autoincrement
  - InnoDB / utf8mb4 / utf8mb4_unicode_ci table args
  - Server-managed timestamps (server_default=func.now())

Relationships:
  User.notes          — deferred to Plan 02/03 when user_id FK is added to notes
  User.refresh_tokens — one-to-many; cascade all, delete-orphan
  RefreshToken.user   — many-to-one back-ref
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Authentication identity — every note, chunk, and collection is owned by a user."""

    __tablename__ = "users"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, autoincrement=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # User.notes relationship deferred to Plan 02/03 when user_id FK is added to notes table.
    # RefreshToken relationship — this migration creates refresh_tokens with user_id FK.
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"


class RefreshToken(Base):
    """Persisted refresh token entry — enables individual token revocation (D-02).

    Each login creates a new row; rotating a refresh token marks the old row
    revoked=True and inserts a new row with the new jti (D-04).
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, autoincrement=True
    )
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id!r} jti={self.jti!r} revoked={self.revoked!r}>"
