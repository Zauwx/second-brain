"""SQLAlchemy ORM model for the Collection entity.

Phase 4 Plan 03 — ORG-03:
  - Collections are per-user (user_id FK → users.id, CASCADE delete).
  - A user cannot have two collections with the same name: UNIQUE(user_id, name).
  - Many-to-many note membership via note_collections join table (defined in
    app/notes/models.py to avoid circular imports).
  - `notes` relationship uses lazy="select"; selectinload added per-query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.notes.models import Note


class Collection(Base):
    """Named collection — the second organization layer for notes."""

    __tablename__ = "collections"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_collection"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Many-to-many notes relationship — lazy="select" (NOT lazy="selectin").
    # selectinload(Note.collections_rel) is added explicitly per-query.
    # secondary references the module-level Table in app.notes.models.
    # overlaps="collections_rel" silences the SQLAlchemy "copies column" warning for
    # the bidirectional pair (Collection.notes ↔ Note.collections_rel).
    notes: Mapped[list[Note]] = relationship(
        "Note",
        secondary="note_collections",
        lazy="select",
        overlaps="collections_rel",
    )

    def __repr__(self) -> str:
        return f"<Collection id={self.id!r} name={self.name!r} user_id={self.user_id!r}>"
