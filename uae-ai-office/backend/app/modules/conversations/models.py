import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

MESSAGE_ROLES: tuple[str, ...] = ("user", "assistant")

message_role = ENUM(*MESSAGE_ROLES, name="message_role", create_type=False)


class Conversation(Base):
    """A single Ask Your Business thread. Creator-private for Step 11 (see
    migration 0014's docstring and app.modules.conversations.repository):
    a conversation is visible only to the user who created it, enforced
    at the database level by RLS, not just by an application-layer
    filter -- even a bug in this module's queries could not leak another
    user's conversation within the same company. The schema itself
    carries nothing that would need to change to later support a shared/
    company-wide conversation; only the RLS policy and the authorization
    check in this module would need to change.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        # Referenced by messages' composite FK below.
        UniqueConstraint("id", "company_id", name="uq_conversations_id_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Message(Base):
    """One turn of a conversation -- either the user's question (role
    'user') or Claude's grounded response (role 'assistant').
    `is_sufficient`/`model_identifier`/`input_tokens`/`output_tokens` are
    only ever set on assistant messages; a user message leaves all four
    NULL. `content` is the exact question text or the exact answer text --
    never a system prompt (Step 11 requirement: system prompts are never
    persisted) and, for an assistant message, never anything beyond what
    was actually returned to the user.
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Referenced by message_citations' composite FK below.
        UniqueConstraint("id", "company_id", name="uq_messages_id_company"),
        # Composite FK against conversations(id, company_id): a message
        # can never claim a company_id that doesn't match its
        # conversation's real company, mirroring
        # document_chunks -> documents.
        ForeignKeyConstraint(
            ["conversation_id", "company_id"],
            ["conversations.id", "conversations.company_id"],
            name="fk_messages_conversation_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    role: Mapped[str] = mapped_column(message_role)
    content: Mapped[str]
    is_sufficient: Mapped[bool | None] = mapped_column(nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class MessageCitation(Base):
    """Exact traceability from one assistant message to the real
    document_chunk row it cited -- the foundation for a future "Show
    source"/"Open document"/"Go to page" feature. Every row here has
    already passed Step 11's citation validation (see ask_service.py)
    before being inserted; this table never holds an unvalidated or
    fabricated citation.
    """

    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "document_chunk_id", name="uq_message_citations_message_chunk"
        ),
        ForeignKeyConstraint(
            ["message_id", "company_id"],
            ["messages.id", "messages.company_id"],
            name="fk_message_citations_message_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_chunk_id", "company_id"],
            ["document_chunks.id", "document_chunks.company_id"],
            name="fk_message_citations_chunk_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    citation_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

