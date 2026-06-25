"""add user_id FK to notes table

Revision ID: 0003_add_user_id_to_notes
Revises: a1b2c3d4e5f6
Create Date: 2026-06-25

Migration sequence (D-11, Pitfall 1 + 2 from RESEARCH.md):
  1. TRUNCATE TABLE notes   — dev data reset; required because the new column is NOT NULL
                              and there is no seed user to backfill (D-11)
  2. add_column user_id nullable — existing table must accept nullable first
  3. create_foreign_key     — FK to users.id ON DELETE CASCADE (users table must exist first
                              per Pitfall 2; guaranteed by down_revision chain to a1b2c3d4e5f6)
  4. alter_column NOT NULL  — safe because table is empty after TRUNCATE
  5. create_index           — query performance for per-user list/count operations

downgrade reverses in opposite order:
  drop_index → drop_constraint → drop_column
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0003_add_user_id_to_notes"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # D-11: Dev data is truncated — no backfill needed.
    # This MUST precede the NOT NULL column addition (Pitfall 1).
    op.execute("TRUNCATE TABLE notes")

    # Step 1: Add column as NOT NULL directly — safe because table is empty after TRUNCATE.
    # Using nullable=False here avoids a second ALTER TABLE that MySQL rejects when a FK
    # constraint already exists on the column (MySQL ER_FK_COLUMN_CANNOT_CHANGE_CHILD).
    op.add_column(
        "notes",
        sa.Column(
            "user_id",
            mysql.INTEGER(unsigned=True),
            nullable=False,
            comment="Owner user — Phase 3 auth seam",
        ),
    )

    # Step 2: Add FK constraint — users table exists because our down_revision points
    # to the create_users_and_refresh_tokens migration (Pitfall 2).
    op.create_foreign_key(
        "fk_notes_user_id",
        "notes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Step 3: Add index for query performance (per-user list queries).
    op.create_index("ix_notes_user_id", "notes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_constraint("fk_notes_user_id", "notes", type_="foreignkey")
    op.drop_column("notes", "user_id")
