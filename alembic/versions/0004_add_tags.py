"""Add tags + note_tags tables; rebuild FULLTEXT index for min_token_size=2.

Revision ID: 0004_add_tags
Revises: 0003_add_user_id_to_notes
Create Date: 2026-06-29

Migration scope (Plan 04-01):
  - tags table: per-user, normalized name, UNIQUE(user_id, name)
  - note_tags join table: composite PK (note_id, tag_id), CASCADE FKs
  - Rebuild ft_notes_content FULLTEXT index so it reindexes at innodb_ft_min_token_size=2

The FULLTEXT index was created by migration d51191e92276 before min_token_size was
configured. DROP + ADD ensures the new index uses the server's current setting (2).
Safe on fresh installs (empty table) and correct on existing DBs.

Note: collections and note_collections are in migration 0005 (Plan 04-02) to keep
each vertical slice's migration self-contained.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0004_add_tags"
down_revision: str | Sequence[str] | None = "0003_add_user_id_to_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_ft_index_if_exists() -> None:
    """DROP the ft_notes_content FULLTEXT index only if it currently exists (WR-04).

    MySQL has no portable ``DROP INDEX IF EXISTS`` for ordinary/FULLTEXT indexes,
    so unconditionally dropping fails hard if an earlier revision never created it
    (or it was renamed/already dropped on a given DB). Check information_schema
    first and make the drop idempotent.
    """
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'notes' "
            "AND index_name = 'ft_notes_content'"
        )
    ).scalar()
    if exists:
        op.execute("ALTER TABLE notes DROP INDEX ft_notes_content")


def upgrade() -> None:
    # 1. tags table — per-user, normalized name, unique per user
    op.create_table(
        "tags",
        sa.Column(
            "id",
            mysql.INTEGER(unsigned=True),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "user_id",
            mysql.INTEGER(unsigned=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_tag"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # 2. note_tags join table — composite PK, CASCADE on both FKs
    op.create_table(
        "note_tags",
        sa.Column("note_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("tag_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.PrimaryKeyConstraint("note_id", "tag_id", name="pk_note_tags"),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        mysql_engine="InnoDB",
    )

    # 3. Rebuild FULLTEXT index with innodb_ft_min_token_size=2 (D-11)
    # The old index was created by d51191e92276 before min_token_size was configured.
    # DROP + ADD ensures the new index uses the server's current min_token_size=2 setting.
    # op.create_index doesn't support FULLTEXT — use raw DDL.
    # The DROP is guarded (WR-04) so the migration does not fail mid-upgrade on a DB
    # where the index was never created / already dropped.
    _drop_ft_index_if_exists()
    op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")


def downgrade() -> None:
    # Restore FULLTEXT index (rebuilt back; no way to restore previous token-size setting)
    _drop_ft_index_if_exists()
    op.execute("ALTER TABLE notes ADD FULLTEXT KEY ft_notes_content (title, content)")
    op.drop_table("note_tags")
    op.drop_table("tags")
