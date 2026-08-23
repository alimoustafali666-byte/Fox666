import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SUPPORT_TICKET_CATEGORIES: tuple[str, ...] = (
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
SUPPORT_TICKET_PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")
SUPPORT_TICKET_STATUSES: tuple[str, ...] = (
    "open",
    "in_progress",
    "waiting_for_user",
    "resolved",
    "closed",
)
SUPPORT_COMMENT_AUTHOR_TYPES: tuple[str, ...] = ("user", "support")

support_ticket_category = ENUM(
    *SUPPORT_TICKET_CATEGORIES, name="support_ticket_category", create_type=False
)
support_ticket_priority = ENUM(
    *SUPPORT_TICKET_PRIORITIES, name="support_ticket_priority", create_type=False
)
support_ticket_status = ENUM(*SUPPORT_TICKET_STATUSES, name="support_ticket_status", create_type=False)
support_comment_author_type = ENUM(
    *SUPPORT_COMMENT_AUTHOR_TYPES, name="support_comment_author_type", create_type=False
)


class SupportTicket(Base):
    """One user's support request. Creator-private, exactly mirroring
    app.modules.conversations.models.Conversation: visible only to the
    user who created it, enforced by RLS (company_id AND created_by both
    match session context), not just an application-layer filter. See
    the Step 17 report for why company-wide (owner/admin) visibility and
    any platform/support-admin cross-tenant access are deliberately NOT
    implemented here.

    `diagnostics` is always built through an explicit allowlist
    (app.modules.support.diagnostics) and re-sanitized through the
    existing app.modules.audit_log.sanitizer.sanitize_metadata before
    being written -- never raw request/response data, never a credential
    or token shape.
    """

    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_support_tickets_id_company"),
        UniqueConstraint("reference_code", name="uq_support_tickets_reference_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(support_ticket_category)
    subject: Mapped[str]
    description: Mapped[str]
    priority: Mapped[str] = mapped_column(support_ticket_priority, server_default="normal")
    status: Mapped[str] = mapped_column(support_ticket_status, server_default="open")
    reference_code: Mapped[str]
    diagnostics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class SupportTicketComment(Base):
    """One reply in a ticket's thread. author_type distinguishes a 'user'
    reply from a future 'support' reply -- Step 17's application code
    only ever writes author_type='user' with a real author_user_id (the
    ticket's own creator); no platform-support actor exists yet, see
    SupportTicket's docstring.
    """

    __tablename__ = "support_ticket_comments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ticket_id", "company_id"],
            ["support_tickets.id", "support_tickets.company_id"],
            name="fk_support_ticket_comments_ticket_company",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    author_type: Mapped[str] = mapped_column(support_comment_author_type)
    body: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

