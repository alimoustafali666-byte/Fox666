"""create daily_briefs, brief_items

Step 12 -- Daily Management Brief (on-demand only; no scheduler/cron/
background job in this step, per approved scope). Two new tenant-owned
tables, per docs/uae-ai-office/ARCHITECTURE.md section 11's approved
schema.

- daily_briefs: one per company per calendar day (UNIQUE(company_id,
  brief_date)) -- "regenerate" replaces the same day's row/items rather
  than creating a duplicate. RLS is plain COMPANY-scoped (unlike Step
  11's creator-private conversations): a brief is a shared, company-wide
  artifact every role may view (per the architecture doc's RBAC table --
  "Ask questions / view brief": all four roles), only regeneration is
  restricted to manager+ at the application layer.

- brief_items: composite FK against daily_briefs(id, company_id)
  (mirroring document_chunks -> documents), plus an OPTIONAL composite FK
  against documents(id, company_id) for source_document_id -- optional
  because the column is nullable (matching the architecture doc's schema
  exactly), but application code (brief_orchestrator) treats every
  generated item as required to cite a real, in-context document before
  it's ever persisted; NULL is reserved for the zero-new-documents
  template case, which is never Claude-generated in the first place.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_ISOLATION_EXPR = (
    "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
)


def upgrade() -> None:
    op.execute("CREATE TYPE brief_item_category AS ENUM "
               "('new_information', 'pending_action', 'follow_up', 'potential_issue')")

    op.create_table(
        "daily_briefs",
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
            "generated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("brief_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("company_id", "brief_date", name="uq_daily_briefs_company_date"),
        sa.UniqueConstraint("id", "company_id", name="uq_daily_briefs_id_company"),
    )
    op.create_index("ix_daily_briefs_company_id", "daily_briefs", ["company_id"])

    op.execute("ALTER TABLE daily_briefs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE daily_briefs FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON daily_briefs USING ({TENANT_ISOLATION_EXPR})")

    op.create_table(
        "brief_items",
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
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "category", postgresql.ENUM(name="brief_item_category", create_type=False), nullable=False
        ),
        sa.Column("text", sa.Text(), nullable=False),
        # No direct ForeignKey() -- the composite constraint below (against
        # documents(id, company_id)) is what enforces referential integrity,
        # the same pattern document_chunks.document_id already uses.
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="2"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["brief_id", "company_id"],
            ["daily_briefs.id", "daily_briefs.company_id"],
            name="fk_brief_items_brief_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id", "company_id"],
            ["documents.id", "documents.company_id"],
            name="fk_brief_items_document_company",
        ),
    )
    op.create_index("ix_brief_items_company_id", "brief_items", ["company_id"])
    op.create_index("ix_brief_items_brief_id", "brief_items", ["brief_id"])

    op.execute("ALTER TABLE brief_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE brief_items FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation ON brief_items USING ({TENANT_ISOLATION_EXPR})")


def downgrade() -> None:
    op.drop_table("brief_items")
    op.drop_table("daily_briefs")
    op.execute("DROP TYPE brief_item_category")

