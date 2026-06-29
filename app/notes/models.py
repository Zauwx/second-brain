"""SQLAlchemy ORM model for the Note entity.

Phase 2 scope:
- Notes have no user_id FK — auth and per-user isolation are added in Phase 3.
- Table uses utf8mb4 / utf8mb4_unicode_ci for full emoji + multilingual support.
- FULLTEXT index on (title, content) is created by the Alembic migration — enables
  MATCH ... AGAINST ... IN BOOLEAN MODE search in Phase 4.

Phase 3 additions:
- `user_id` FK → users.id (NOT NULL, indexed) — per-user data isolation (D-07)
- `owner` relationship back-refs to User.notes (added when FK migration lands)

Column notes:
- `title`      VARCHAR(512)  — nullable; a note may be content-only (e.g., a quick clip)
- `content`    LONGTEXT      — NOT NULL; the primary data
- `source_url` VARCHAR(2048) — nullable; URL of the original article/page
- `user_id`    INTEGER UNSIGNED — NOT NULL FK → users.id; owner of the note
- `created_at` / `updated_at` — managed by the DB (DEFAULT / ON UPDATE CURRENT_TIMESTAMP)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.auth.models import User
    from app.tags.models import Tag


# ---------------------------------------------------------------------------
# Association table: note_tags (many-to-many: Note ↔ Tag)
# Defined at module level as a Core Table object (not an ORM class) so it can
# be used as the `secondary` argument in the relationship below.
# String FK refs ("tags.id") defer resolution to mapper-configure time — no
# circular import at module load.
# ---------------------------------------------------------------------------
note_collections = Table(
    "note_collections",
    Base.metadata,
    Column(
        "note_id",
        INTEGER(unsigned=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "collection_id",
        INTEGER(unsigned=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    mysql_engine="InnoDB",
)

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column(
        "note_id",
        INTEGER(unsigned=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        INTEGER(unsigned=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    mysql_engine="InnoDB",
)


class Note(Base):
    """Core note entity — the primary record in the second-brain store."""

    __tablename__ = "notes"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), primary_key=True, autoincrement=True
    )
    title: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="Optional note title"
    )
    content: Mapped[str] = mapped_column(
        Text(length=4294967295),  # LONGTEXT — up to 4 GB
        nullable=False,
        comment="Main note content",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, comment="URL of the original source"
    )
    user_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owner user — added Phase 3",
    )
    owner: Mapped[User] = relationship("User", back_populates="notes")
    # Many-to-many tags relationship — lazy="select" (NOT lazy="selectin").
    # selectinload(Note.tags) is added explicitly in each async query to avoid
    # N+1 and MissingGreenlet errors (Pattern 2, RESEARCH.md).
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=note_tags, lazy="select"
    )
    # Many-to-many collections relationship — lazy="select".
    # selectinload added per-query where needed.
    # overlaps="notes" silences the SQLAlchemy "copies column" warning for the
    # bidirectional relationship pair (Collection.notes ↔ Note.collections_rel).
    collections_rel: Mapped[list[Collection]] = relationship(
        "Collection", secondary=note_collections, lazy="select", overlaps="notes"
    )
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

    def __repr__(self) -> str:
        return f"<Note id={self.id!r} title={self.title!r}>"


# ---------------------------------------------------------------------------
# Ensure Collection is registered in the SQLAlchemy mapper registry so that
# Note.collections_rel can resolve "Collection" at mapper-configure time.
# This import is safe: app.collections.models only imports Note under
# TYPE_CHECKING at runtime — no circular dependency chain.
# ---------------------------------------------------------------------------
from app.collections.models import Collection as _Collection  # noqa: F401, E402
