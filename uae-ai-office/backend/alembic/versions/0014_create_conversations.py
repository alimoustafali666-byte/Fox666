"""create conversations, messages, message_citations

Step 11 -- Ask Your Business. Three new tenant-owned tables, plus one
prerequisite change to document_chunks:

- uq_document_chunks_id_company: a composite UNIQUE(id, company_id) on
  the existing document_chunks table, mirroring uq_documents_id_company
  (migration 0010). Postgres requires the referenced side of a composite
  foreign key to be backed by a unique constraint on exactly those
  columns; message_citations(document_chunk_id, company_id) below
  references this one.

- conversations: one Ask Your Business thread. RLS is CREATOR-PRIVATE,
  not merely company-scoped like every other tenant_isolation policy so
  far (documents, projects, document_chunks, audit_logs) -- per the
  approved Step 11 design ("prefer creator-private unless there is a
  strong business reason otherwise"). The policy requires BOTH
  company_id AND created_by to match the session's context
  (app.current_company_id AND app.current_user_id, the latter already
  set by every authenticated request -- see migration 0007's docstring
  for where app.current_user_id comes from), combined with AND in a
  single USING clause -- not two OR'd permissive policies like
  company_members' self-lookup policy, since here both conditions must
  hold, not either. A user in the same company genuinely cannot read
  another user's conversation, at the database level, even if
  application code has a bug. The schema itself needs no change to
  support a future shared/company-wide conversation -- only this RLS
  policy (and the corresponding application-layer authorization check)
  would need to change.

- messages: belongs to exactly one conversation (composite FK against
  conversations(id, company_id), mirroring document_chunks ->
  documents). Its own RLS policy re-derives creator-private access via
  an EXISTS subquery against conversations, rather than duplicating
  created_by onto this table -- messages have no independent owner
  outside their conversation, so this keeps that single fact in one
  place. role is a new Postgres enum (message_role: user, assistant),
  the same style as documents.document_type.

- message_citations: exact traceability from one assistant message to
  the real document_chunks row it cited (never persisted for a fabricated
  or unvalidated citation -- see app.modules.conversations.ask_service).
  Composite FKs against both messages(id, company_id) and
  document_chunks(id, company_id), so a citation can never claim a
  company_id mismatched with either its message or the chunk it points
  to. Its RLS policy re-derives creator-private access the same way,
  via messages -> conversations.

Cascade behavior: ON DELETE CASCADE throughout (companies -> ... and the
composite FKs), consistent with document_chunks -- no code path performs
a hard delete of a conversation/message today; this only protects a
future retention/cleanup job from leaving orphaned rows.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPANY_EXPR = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid"
_USER_EXPR = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_chunks_id_company", "document_chunks", ["id", "company_id"]
    )

    op.execute("CREATE TYPE message_role AS ENUM ('user', 'assistant')")

    op.create_table(
        "conversations",
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
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_conversations_id_company"),
    )
    op.create_index("ix_conversations_company_id", "conversations", ["company_id"])
    op.create_index("ix_conversations_created_by", "conversations", ["created_by"])

    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON conversations "
        f"USING ({_COMPANY_EXPR} AND created_by = {_USER_EXPR})"
    )

    op.create_table(
        "messages",
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
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", postgresql.ENUM(name="message_role", create_type=False), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_sufficient", sa.Boolean(), nullable=True),
        sa.Column("model_identifier", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("id", "company_id", name="uq_messages_id_company"),
        sa.ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["conversations.id", "conversations.company_id"],
            name="fk_messages_conversation_company",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_messages_company_id", "messages", ["company_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE messages FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON messages "
        f"USING ({_COMPANY_EXPR} AND EXISTS ("
        f"SELECT 1 FROM conversations c "
        f"WHERE c.id = messages.conversation_id AND c.created_by = {_USER_EXPR}"
        f"))"
    )

    op.create_table(
        "message_citations",
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
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citation_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint(
            "message_id", "document_chunk_id", name="uq_message_citations_message_chunk"
        ),
        sa.ForeignKeyConstraint(
            ["message_id", "company_id"],
            ["messages.id", "messages.company_id"],
            name="fk_message_citations_message_company",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id", "company_id"],
            ["document_chunks.id", "document_chunks.company_id"],
            name="fk_message_citations_chunk_company",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_message_citations_company_id", "message_citations", ["company_id"])
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])

    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_citations FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON message_citations "
        f"USING ({_COMPANY_EXPR} AND EXISTS ("
        f"SELECT 1 FROM messages m "
        f"JOIN conversations c ON c.id = m.conversation_id "
        f"WHERE m.id = message_citations.message_id AND c.created_by = {_USER_EXPR}"
        f"))"
    )


def downgrade() -> None:
    op.drop_table("message_citations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP TYPE message_role")
    op.drop_constraint("uq_document_chunks_id_company", "document_chunks", type_="unique")

