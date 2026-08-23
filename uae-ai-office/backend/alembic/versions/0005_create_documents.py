"""create documents

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_ISOLATION_EXPR = (
    "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE document_type AS ENUM "
        "('contract', 'boq', 'quotation', 'invoice', 'purchase_order', "
        "'project_report', 'other')"
    )

    op.create_table(
        "documents",
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
        # No direct ForeignKey() here -- the composite constraint below is
        # what actually enforces referential integrity for this column, and
        # also ties it to company_id.
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "document_type",
            postgresql.ENUM(
                "contract", "boq", "quotation", "invoice", "purchase_order",
                "project_report", "other",
                name="document_type", create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
        # Free text, not an enum: Phase 1 only ever writes 'uploaded', but
        # future ingestion states (processing/processed/failed) can be
        # added without a migration to widen a CHECK/enum.
        sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
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
        # Soft delete: rows are marked, never physically removed, in Phase 1.
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        # Composite FK: if project_id is set, the referenced project's
        # company_id MUST equal this row's company_id, enforced by Postgres
        # itself -- a document can never point at another company's
        # project, even if application code has a bug. A NULL project_id
        # (company-level document) satisfies the constraint trivially
        # (Postgres MATCH SIMPLE semantics: any NULL in a composite FK
        # skips the check), which is the intended behavior.
        sa.ForeignKeyConstraint(
            ["project_id", "company_id"],
            ["projects.id", "projects.company_id"],
            name="fk_documents_project_company",
        ),
    )
    op.create_index("ix_documents_company_id", "documents", ["company_id", "created_at"])
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON documents USING ({TENANT_ISOLATION_EXPR})")


def downgrade() -> None:
    op.drop_table("documents")
    op.execute("DROP TYPE document_type")

