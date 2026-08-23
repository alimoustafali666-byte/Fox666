"""create support_tickets, support_ticket_comments

Step 17 -- Support Center foundation. Two new tenant-owned tables,
deliberately mirroring the Step 11 conversations/messages design exactly:

- support_tickets: one user's support request. RLS is CREATOR-PRIVATE,
  identical in shape to conversations' policy (both company_id AND
  created_by must match the session's context) -- the simplest, safest
  MVP privacy model per the approved Step 17 design ("prefer
  creator-private unless there is a clear reason for company-wide
  visibility"). No platform/support-admin role or cross-tenant access
  exists anywhere in this migration or the application code built on top
  of it -- see the Step 17 report for why that is deliberately deferred
  rather than implemented or simulated.

- support_ticket_comments: belongs to exactly one ticket (composite FK
  against support_tickets(id, company_id), mirroring messages ->
  conversations). Its RLS policy re-derives creator-private access via
  an EXISTS subquery against support_tickets, the same pattern messages'
  policy uses via conversations. author_type distinguishes a 'user'
  reply from a future 'support' reply; author_user_id is nullable to
  leave room for a future system/support actor that isn't a company
  member, but Step 17's application code only ever writes author_type
  = 'user' with a real author_user_id (the ticket's own creator).

reference_code is a short, human-quotable, globally-unique code (e.g.
"REF-7F3K2Q") -- the concrete "I have ticket REF-ABC123" correlation
mechanism from the Step 17 spec; generated and validated unique by the
application layer, not the database (see app.modules.support.service).

diagnostics is JSONB, always allowlist-built and re-sanitized through
the existing app.modules.audit_log.sanitizer.sanitize_metadata before
being written -- never raw request/response data.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-22

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPANY_EXPR = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
_USER_EXPR = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"

_CATEGORIES = (
    "getting_started",
    "account_login",
    "projects",
    "documents",
    "upload_processing_indexing",
    "ask_your_business",
    "daily_brief",
    "language_settings",
    "roles_permissions",
    "troubleshooting",
    "other",
)
_PRIORITIES = ("low", "normal", "high", "urgent")
_STATUSES = ("open", "in_progress", "waiting_for_user", "resolved", "closed")
_AUTHOR_TYPES = ("user", "support")


def upgrade() -> None:
    category_list = ", ".join(f"'{c}'" for c in _CATEGORIES)
    op.execute(f"CREATE TYPE support_ticket_category AS ENUM ({category_list})")
    op.execute("CREATE TYPE support_ticket_priority AS ENUM ('low', 'normal', 'high', 'urgent')")
    op.execute(
        "CREATE TYPE support_ticket_status AS ENUM "
        "('open', 'in_progress', 'waiting_for_user', 'resolved', 'closed')"
    )
    op.execute("CREATE TYPE support_comment_author_type AS ENUM ('user', 'support')")

    op.create_table(
        "support_tickets",
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
            "created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "category",
            postgresql.ENUM(*_CATEGORIES, name="support_ticket_category", create_type=False),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            postgresql.ENUM(*_PRIORITIES, name="support_ticket_priority", create_type=False),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_STATUSES, name="support_ticket_status", create_type=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("reference_code", sa.Text(), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("id", "company_id", name="uq_support_tickets_id_company"),
        sa.UniqueConstraint("reference_code", name="uq_support_tickets_reference_code"),
    )
    op.create_index("ix_support_tickets_company_id", "support_tickets", ["company_id"])
    op.create_index("ix_support_tickets_created_by", "support_tickets", ["created_by"])
    op.create_index(
        "ix_support_tickets_reference_code", "support_tickets", ["reference_code"], unique=True
    )

    op.execute("ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE support_tickets FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON support_tickets "
        f"USING ({_COMPANY_EXPR} AND created_by = {_USER_EXPR})"
    )

    op.create_table(
        "support_ticket_comments",
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
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "author_type",
            postgresql.ENUM(*_AUTHOR_TYPES, name="support_comment_author_type", create_type=False),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id", "company_id"],
            ["support_tickets.id", "support_tickets.company_id"],
            name="fk_support_ticket_comments_ticket_company",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_support_ticket_comments_company_id", "support_ticket_comments", ["company_id"]
    )
    op.create_index(
        "ix_support_ticket_comments_ticket_id", "support_ticket_comments", ["ticket_id"]
    )

    op.execute("ALTER TABLE support_ticket_comments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE support_ticket_comments FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON support_ticket_comments "
        f"USING ({_COMPANY_EXPR} AND EXISTS ("
        f"SELECT 1 FROM support_tickets t "
        f"WHERE t.id = support_ticket_comments.ticket_id AND t.created_by = {_USER_EXPR}"
        f"))"
    )


def downgrade() -> None:
    op.drop_table("support_ticket_comments")
    op.drop_table("support_tickets")
    op.execute("DROP TYPE support_comment_author_type")
    op.execute("DROP TYPE support_ticket_status")
    op.execute("DROP TYPE support_ticket_priority")
    op.execute("DROP TYPE support_ticket_category")

