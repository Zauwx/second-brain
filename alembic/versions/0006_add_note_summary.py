"""Add nullable summary column to notes table.

Revision ID: 0006_add_note_summary
Revises: 0005_add_collections
Create Date: 2026-07-06

Migration scope (Plan 05-03, D-02):
  - notes.summary — nullable TEXT column, populated by POST /ai/summarize.

Simple add/drop-column migration — no FK, no backfill needed since the
column is nullable and starts empty for all existing notes.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_add_note_summary"
down_revision: str | Sequence[str] | None = "0005_add_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="AI-generated summary (Phase 5, D-02)",
        ),
    )


def downgrade() -> None:
    op.drop_column("notes", "summary")
