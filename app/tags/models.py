"""SQLAlchemy ORM model for the Tag entity.

Phase 4 (Plan 01) scope:
- Tags are per-user entities — each user has a private tag namespace.
- Tag names are normalized (trimmed + lowercased) at the service/repository layer.
- UNIQUE(user_id, name) enforces the one-tag-per-name-per-user invariant in the DB.

Column notes:
- `id`      UNSIGNED INT PK, autoincrement
- `user_id` FK → users.id ON DELETE CASCADE, indexed for per-user list queries
- `name`    VARCHAR(128) NOT NULL — stored normalized (lowercase, stripped)
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tag(Base):
    """Per-user tag entity — the name is normalized on ingest."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag"),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    def __repr__(self) -> str:
        return f"<Tag id={self.id!r} name={self.name!r} user_id={self.user_id!r}>"
