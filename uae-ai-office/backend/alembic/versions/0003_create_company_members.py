"""create company_members

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every RLS policy in Phase 1 shares this expression: NULLIF(...) turns an
# absent/empty session variable into NULL, and `column = NULL` is always
# UNKNOWN (never true) in SQL -- so a missing/blank company context yields
# zero rows rather than an error. An invalid (non-UUID) context still
# raises on the ::uuid cast, which is acceptable: that can only happen if
# application code is already broken, and failing loudly beats silently
# returning no rows for a bug that should be caught in testing.
TENANT_ISOLATION_EXPR = (
    "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE company_role AS ENUM ('owner', 'admin', 'manager', 'member')"
    )

    op.create_table(
        "company_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "admin", "manager", "member", name="company_role", create_type=False),
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_members_company_id_user_id"),
    )
    op.create_index("ix_company_members_company_id", "company_members", ["company_id"])

    op.execute("ALTER TABLE company_members ENABLE ROW LEVEL SECURITY")
    # FORCE so RLS also applies to the table owner (the app's own DB role),
    # not just other roles -- only a superuser bypasses RLS regardless.
    op.execute("ALTER TABLE company_members FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON company_members USING ({TENANT_ISOLATION_EXPR})"
    )


def downgrade() -> None:
    op.drop_table("company_members")
    op.execute("DROP TYPE company_role")

