"""create projects

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_ISOLATION_EXPR = (
    "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE project_status AS ENUM "
        "('planning', 'active', 'on_hold', 'completed', 'cancelled')"
    )

    op.create_table(
        "projects",
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
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("project_code", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "planning", "active", "on_hold", "completed", "cancelled",
                name="project_status", create_type=False,
            ),
            nullable=False,
            server_default="planning",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # NULLs are never equal in a UNIQUE constraint, so any number of
        # projects with no code coexist per company; two projects in the
        # same company can never share a non-null code.
        sa.UniqueConstraint("company_id", "project_code", name="uq_projects_company_code"),
        # Referenced by documents' composite FK (next migration) so a
        # document can never be attached to another company's project.
        sa.UniqueConstraint("id", "company_id", name="uq_projects_id_company"),
    )
    op.create_index("ix_projects_company_id", "projects", ["company_id"])

    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE projects FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON projects USING ({TENANT_ISOLATION_EXPR})")


def downgrade() -> None:
    op.drop_table("projects")
    op.execute("DROP TYPE project_status")

