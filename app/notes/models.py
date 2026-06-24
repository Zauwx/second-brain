"""SQLAlchemy ORM model for the Note entity.

Phase 2 scope:
- Notes have no user_id FK — auth and per-user isolation are added in Phase 3.
- Table uses utf8mb4 / utf8mb4_unicode_ci for full emoji + multilingual support.
- FULLTEXT index on (title, content) is created by the Alembic migration — enables
  MATCH ... AGAINST ... IN BOOLEAN MODE search in Phase 4.

Column notes:
- `title`      VARCHAR(512)  — nullable; a note may be content-only (e.g., a quick clip)
- `content`    LONGTEXT      — NOT NULL; the primary data
- `source_url` VARCHAR(2048) — nullable; URL of the original article/page
- `created_at` / `updated_at` — managed by the DB (DEFAULT / ON UPDATE CURRENT_TIMESTAMP)
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
