"""create document_chunks

Tenant-owned, RLS-enforced storage for the deterministic output of the
Step 9 processing pipeline (extract -> normalize -> chunk). No
embedding/vector column yet -- that's a later, explicitly separate step.

Referential integrity: (document_id, company_id) is a composite FK
against documents(id, company_id) -- see migration 0010's
uq_documents_id_company -- so a chunk can never claim a company_id that
doesn't match its document's real company, even if application code has
a bug (the same defense documents(project_id, company_id) already gets
against projects).

Cascade behavior, considered deliberately because documents are
soft-deleted rather than physically removed: a soft delete (an UPDATE of
documents.deleted_at) never touches document_chunks at all, exactly like
soft-deleting a document today leaves its storage object in place --
existing chunks of a soft-deleted document simply remain, inaccessible
the same way the document itself becomes. ON DELETE CASCADE on the
composite FK only matters for a documents row being physically deleted,
which no code path performs today; it exists so that IF a future
retention/cleanup job ever does hard-delete a documents row, its chunks
are cleaned up automatically rather than becoming orphaned rows with no
owning document -- not a behavior this step's application code triggers.
company_id also cascades directly from companies, consistent with every
other tenant-owned table.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_ISOLATION_EXPR = (
    "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        "document_chunks",
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
        # No direct ForeignKey() here -- the composite constraint below
        # (against documents(id, company_id)) is what enforces referential
        # integrity for this column, the same pattern documents.project_id
        # already uses against projects.
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("sheet_name", sa.Text(), nullable=True),
        sa.Column("section_name", sa.Text(), nullable=True),
        sa.Column("source_location", postgresql.JSONB(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
        sa.ForeignKeyConstraint(
            ["document_id", "company_id"],
            ["documents.id", "documents.company_id"],
            name="fk_document_chunks_document_company",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_document_chunks_company_id", "document_chunks", ["company_id"])
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON document_chunks USING ({TENANT_ISOLATION_EXPR})"
    )


def downgrade() -> None:
    op.drop_table("document_chunks")

