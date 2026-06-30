"""Add collections + note_collections tables.

Revision ID: 0005_add_collections
Revises: 0004_add_tags
Create Date: 2026-06-29

Migration scope (Plan 04-03):
  - collections table: per-user, name VARCHAR(255), UNIQUE(user_id, name)
  - note_collections join table: composite PK (note_id, collection_id), CASCADE FKs

Chains from 0004_add_tags (tags + note_tags). This migration is kept separate to
preserve vertical-slice self-containment per decision [Phase 04 Plan 01].
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0005_add_collections"
down_revision: str | Sequence[str] | None = "0004_add_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. collections table — per-user, named, UNIQUE(user_id, name)
    op.create_table(
        "collections",
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_collection"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # 2. note_collections join table — composite PK, CASCADE on both FKs
    op.create_table(
        "note_collections",
        sa.Column("note_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("collection_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.PrimaryKeyConstraint("note_id", "collection_id", name="pk_note_collections"),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        mysql_engine="InnoDB",
    )


def downgrade() -> None:
    op.drop_table("note_collections")
    op.drop_table("collections")
