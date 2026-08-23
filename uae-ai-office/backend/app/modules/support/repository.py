import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.support.models import SupportTicket, SupportTicketComment


def create_ticket(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    created_by: uuid.UUID,
    category: str,
    subject: str,
    description: str,
    priority: str,
    reference_code: str,
    diagnostics: dict | None,
) -> SupportTicket:
    now = datetime.now(UTC)
    ticket = SupportTicket(
        id=id,
        company_id=company_id,
        created_by=created_by,
        category=category,
        subject=subject,
        description=description,
        priority=priority,
        status="open",
        reference_code=reference_code,
        diagnostics=diagnostics,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    db.flush()
    return ticket


def get_ticket_by_id(
    db: Session, *, company_id: uuid.UUID, created_by: uuid.UUID, ticket_id: uuid.UUID
) -> SupportTicket | None:
    """The `created_by` filter here is defense-in-depth on top of RLS,
    same rationale as app.modules.conversations.repository.get_conversation_by_id.
    """
    return db.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.company_id == company_id,
            SupportTicket.created_by == created_by,
        )
    ).scalar_one_or_none()


def reference_code_exists(db: Session, *, reference_code: str) -> bool:
    """Checked before insert to avoid a rare collision on the short
    reference_code space; RLS does not hide this check from the caller's
    own company context, but reference_code is globally unique across all
    companies (uq_support_tickets_reference_code), and a Session only
    ever has one company's RLS context active -- so a genuine cross-
    company collision would need a second, direct existence check. In
    practice this only ever needs to catch a collision within the
    currently active session's own visibility; app.modules.support.service
    additionally accepts a database IntegrityError as the authoritative
    final check.
    """
    return (
        db.execute(
            select(SupportTicket.id).where(SupportTicket.reference_code == reference_code)
        ).first()
        is not None
    )


def list_tickets(
    db: Session,
    *,
    company_id: uuid.UUID,
    created_by: uuid.UUID,
    limit: int,
    status: str | None = None,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[SupportTicket]:
    query = select(SupportTicket).where(
        SupportTicket.company_id == company_id, SupportTicket.created_by == created_by
    )
    if status is not None:
        query = query.where(SupportTicket.status == status)
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                SupportTicket.created_at < cursor_created_at,
                and_(
                    SupportTicket.created_at == cursor_created_at, SupportTicket.id < cursor_id
                ),
            )
        )
    query = query.order_by(SupportTicket.created_at.desc(), SupportTicket.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def update_ticket_status(
    db: Session, ticket: SupportTicket, *, status: str, resolved: bool
) -> SupportTicket:
    ticket.status = status
    ticket.updated_at = datetime.now(UTC)
    if resolved:
        ticket.resolved_at = datetime.now(UTC)
    db.flush()
    return ticket


def create_comment(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    ticket_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    author_type: str,
    body: str,
) -> SupportTicketComment:
    comment = SupportTicketComment(
        id=id,
        company_id=company_id,
        ticket_id=ticket_id,
        author_user_id=author_user_id,
        author_type=author_type,
        body=body,
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    db.flush()
    return comment


def list_comments(
    db: Session, *, company_id: uuid.UUID, ticket_id: uuid.UUID
) -> list[SupportTicketComment]:
    return list(
        db.execute(
            select(SupportTicketComment)
            .where(
                SupportTicketComment.company_id == company_id,
                SupportTicketComment.ticket_id == ticket_id,
            )
            .order_by(SupportTicketComment.created_at.asc(), SupportTicketComment.id.asc())
        ).scalars()
    )

