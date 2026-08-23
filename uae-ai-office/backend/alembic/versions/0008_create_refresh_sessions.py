"""create refresh_sessions

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-21

No RLS on this table, deliberately: it's an internal auth/session table,
never joined into company-facing "list our data" queries, and every
access pattern looks it up directly by token_hash (a unique, unguessable
value) or by user_id -- both filters the auth module applies explicitly
in code. Same reasoning as `users` having no RLS.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 of the raw opaque refresh token -- the raw token is
        # never persisted anywhere.
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        # Shared across a chain of rotated tokens. On reuse detection
        # (a revoked token presented again), every session sharing this
        # family_id is revoked, on the assumption the whole chain is
        # compromised.
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # The session that replaced this one via rotation, if any.
        sa.Column(
            "replaced_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("refresh_sessions.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_family_id", "refresh_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_table("refresh_sessions")

