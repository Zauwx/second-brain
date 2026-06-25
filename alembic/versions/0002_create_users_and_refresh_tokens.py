"""create users and refresh_tokens tables

Revision ID: 0002_create_users_and_refresh_tokens
Revises: d51191e92276
Create Date: 2026-06-25

Tables created:
  users          — authentication identity (email UNIQUE, hashed_password, timestamps)
  refresh_tokens — persisted JTI values enabling per-token revocation (D-02, D-05)

Table conventions:
  - InnoDB / utf8mb4 / utf8mb4_unicode_ci (mirrors notes table)
  - INTEGER UNSIGNED PKs with autoincrement
  - Server-managed CURRENT_TIMESTAMP defaults

Indexes:
  - ix_users_email         (users.email, UNIQUE) — lookup by email on every login
  - ix_refresh_tokens_jti  (refresh_tokens.jti, UNIQUE) — lookup by jti on refresh/logout
  - ix_refresh_tokens_user_id (refresh_tokens.user_id) — lookup all tokens for a user

FK: refresh_tokens.user_id → users.id ON DELETE CASCADE
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d51191e92276"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users and refresh_tokens tables."""

    # ------------------------------------------------------------------
    # users table
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, comment="Unique user email"),
        sa.Column(
            "hashed_password",
            sa.String(255),
            nullable=False,
            comment="Argon2id hash — never store plaintext",
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # refresh_tokens table
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", mysql.INTEGER(unsigned=True), primary_key=True, autoincrement=True),
        sa.Column("jti", sa.String(36), nullable=False, comment="JWT ID — UUID4 string"),
        sa.Column(
            "user_id",
            mysql.INTEGER(unsigned=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Owner user",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="True once token is rotated or logged out",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp when this token was revoked",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_refresh_tokens_jti", "refresh_tokens", ["jti"], unique=True)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    """Drop refresh_tokens then users (reverse FK order)."""
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_jti", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
