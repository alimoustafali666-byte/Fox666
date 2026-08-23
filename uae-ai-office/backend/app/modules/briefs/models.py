import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, SmallInteger, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BRIEF_ITEM_CATEGORIES: tuple[str, ...] = (
    "new_information", "pending_action", "follow_up", "potential_issue",
)

brief_item_category = ENUM(*BRIEF_ITEM_CATEGORIES, name="brief_item_category", create_type=False)


class DailyBrief(Base):
    """One per company per calendar day (UNIQUE(company_id, brief_date)) --
    on-demand only in Step 12: created/replaced by POST /v1/briefs/regenerate,
    never by a scheduler. RLS is plain company-scoped (not creator-private
    like Step 11's conversations): a brief is a shared artifact every role
    may view.
    """

    __tablename__ = "daily_briefs"
    __table_args__ = (
        UniqueConstraint("company_id", "brief_date", name="uq_daily_briefs_company_date"),
        UniqueConstraint("id", "company_id", name="uq_daily_briefs_id_company"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    brief_date: Mapped[date] = mapped_column(Date)
    summary: Mapped[str]
    generated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class BriefItem(Base):
    """One categorized, document-grounded item within a brief.
    `source_document_id` is nullable only for schema reasons (matches the
    approved architecture doc exactly); brief_orchestrator never persists
    a Claude-generated item without a validated source -- the only items
    that ever have a NULL source are the fixed "no new documents" template
    brief's zero items, which is a distinct code path that never involves
    Claude at all.
    """

    __tablename__ = "brief_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["brief_id", "company_id"],
            ["daily_briefs.id", "daily_briefs.company_id"],
            name="fk_brief_items_brief_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_document_id", "company_id"],
            ["documents.id", "documents.company_id"],
            name="fk_brief_items_document_company",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    brief_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    category: Mapped[str] = mapped_column(brief_item_category)
    text: Mapped[str]
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, server_default="2")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

