"""create notes table

Revision ID: d51191e92276
Revises:
Create Date: 2026-06-24 14:48:17.917414

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d51191e92276"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the notes table with utf8mb4 charset and InnoDB engine.

    Columns:
      - id          UNSIGNED INT PK AUTO_INCREMENT
      - title       VARCHAR(512) nullable
      - content     LONGTEXT NOT NULL
      - source_url  VARCHAR(2048) nullable
      - created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
      - updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP

    Indexes:
      - FULLTEXT KEY ft_content (title, content) — enables MATCH AGAINST search in Phase 4
        (added via raw SQL because Alembic has limited FULLTEXT support)

    Note: user_id FK is intentionally absent — auth is added in Phase 3.
    """
    op.create_table(
        "notes",
        sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(512), nullable=True, comment="Optional note title"),
        sa.Column(
            "content",
            sa.Text(length=4294967295),  # LONGTEXT
            nullable=False,
            comment="Main note content",
        ),
        sa.Column(
            "source_url", sa.String(2048), nullable=True, comment="URL of the original source"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    # Add FULLTEXT index for Phase 4 full-text search feature.
    # op.create_index doesn't support FULLTEXT — use raw DDL.
    op.execute(
        "ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)"
    )


def downgrade() -> None:
    """Drop the notes table."""
    op.drop_table("notes")
