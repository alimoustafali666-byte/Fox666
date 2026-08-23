import secrets
import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit_log.service import record_audit_event
from app.modules.auth.service import TenantContext
from app.modules.support import repository
from app.modules.support.diagnostics import DiagnosticsInput, build_diagnostics
from app.modules.support.exceptions import (
    InvalidTicketStatusTransitionError,
    SupportTicketNotFoundError,
    SupportTicketRateLimitedError,
)
from app.modules.support.models import SupportTicket, SupportTicketComment
from app.modules.support.rate_limit import ticket_create_rate_limiter

# Excludes visually-ambiguous characters (0/O, 1/I) -- a reference code is
# meant to be read aloud or typed by a customer.
_REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_REFERENCE_LENGTH = 6
_REFERENCE_GENERATION_ATTEMPTS = 5


def _generate_reference_code(db: Session) -> str:
    for _ in range(_REFERENCE_GENERATION_ATTEMPTS):
        code = "REF-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(_REFERENCE_LENGTH))
        if not repository.reference_code_exists(db, reference_code=code):
            return code
    # Astronomically unlikely with a ~1B-combination space checked against
    # a tiny table, but never silently reuse a colliding code.
    raise RuntimeError("Could not generate a unique support ticket reference code.")


def create_ticket(
    db: Session,
    *,
    context: TenantContext,
    category: str,
    subject: str,
    description: str,
    priority: str,
    diagnostics_input: DiagnosticsInput | None,
    ip_address: str | None,
) -> SupportTicket:
    if ticket_create_rate_limiter.is_locked(str(context.user.id)):
        raise SupportTicketRateLimitedError(
            "Too many support tickets created recently. Please try again later."
        )

    diagnostics = (
        build_diagnostics(db, context=context, data=diagnostics_input)
        if diagnostics_input is not None
        else None
    )

    reference_code = _generate_reference_code(db)

    try:
        ticket = repository.create_ticket(
            db,
            id=uuid.uuid4(),
            company_id=context.company_id,
            created_by=context.user.id,
            category=category,
            subject=subject,
            description=description,
            priority=priority,
            reference_code=reference_code,
            diagnostics=diagnostics,
        )
    except IntegrityError:
        # Extremely rare race on reference_code's global uniqueness --
        # one bounded retry with a fresh code rather than surfacing a raw
        # database error to the client.
        db.rollback()
        reference_code = _generate_reference_code(db)
        ticket = repository.create_ticket(
            db,
            id=uuid.uuid4(),
            company_id=context.company_id,
            created_by=context.user.id,
            category=category,
            subject=subject,
            description=description,
            priority=priority,
            reference_code=reference_code,
            diagnostics=diagnostics,
        )

    record_audit_event(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        action="support.ticket_created",
        resource_type="support_ticket",
        resource_id=ticket.id,
        metadata={
            "category": category,
            "priority": priority,
            "reference_code": reference_code,
            "has_diagnostics": diagnostics is not None and len(diagnostics) > 0,
        },
        ip_address=ip_address,
    )
    db.commit()
    ticket_create_rate_limiter.record_failure(str(context.user.id))
    return ticket


def get_ticket(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, ticket_id: uuid.UUID
) -> SupportTicket:
    ticket = repository.get_ticket_by_id(
        db, company_id=company_id, created_by=actor_user_id, ticket_id=ticket_id
    )
    if ticket is None:
        raise SupportTicketNotFoundError("Support ticket not found.")
    return ticket


def list_tickets(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    limit: int,
    status: str | None,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[SupportTicket]:
    return repository.list_tickets(
        db,
        company_id=company_id,
        created_by=actor_user_id,
        limit=limit,
        status=status,
        cursor=cursor,
    )


def list_comments(
    db: Session, *, company_id: uuid.UUID, ticket_id: uuid.UUID
) -> list[SupportTicketComment]:
    return repository.list_comments(db, company_id=company_id, ticket_id=ticket_id)


def add_comment(
    db: Session,
    *,
    context: TenantContext,
    ticket_id: uuid.UUID,
    body: str,
    ip_address: str | None,
) -> SupportTicketComment:
    ticket = get_ticket(
        db, company_id=context.company_id, actor_user_id=context.user.id, ticket_id=ticket_id
    )

    comment = repository.create_comment(
        db,
        id=uuid.uuid4(),
        company_id=context.company_id,
        ticket_id=ticket.id,
        author_user_id=context.user.id,
        author_type="user",
        body=body,
    )
    ticket.updated_at = comment.created_at
    db.flush()

    record_audit_event(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        action="support.ticket_replied",
        resource_type="support_ticket",
        resource_id=ticket.id,
        metadata={"author_type": "user", "comment_id": str(comment.id)},
        ip_address=ip_address,
    )
    db.commit()
    return comment


def update_ticket_status(
    db: Session,
    *,
    context: TenantContext,
    ticket_id: uuid.UUID,
    new_status: str,
    ip_address: str | None,
) -> SupportTicket:
    """Step 17 exposes exactly one transition: the ticket's own creator
    may close their own open/in-progress/waiting-for-user ticket. Every
    other target status (in_progress, waiting_for_user, resolved) is
    rejected -- those legitimately belong to a support agent acting on
    the ticket, and no such actor exists in this release (see the Step
    17 report's "architecture decisions still needed" section). This is
    an application-layer policy choice, not a schema limitation: the
    column and enum already support all five statuses so a future
    support-admin capability needs no migration to use them.
    """
    if new_status != "closed":
        raise InvalidTicketStatusTransitionError(
            "Only closing your own ticket is supported in this release."
        )

    ticket = get_ticket(
        db, company_id=context.company_id, actor_user_id=context.user.id, ticket_id=ticket_id
    )
    if ticket.status == "closed":
        raise InvalidTicketStatusTransitionError("This ticket is already closed.")

    previous_status = ticket.status
    repository.update_ticket_status(db, ticket, status="closed", resolved=False)

    record_audit_event(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        action="support.ticket_status_changed",
        resource_type="support_ticket",
        resource_id=ticket.id,
        metadata={"from_status": previous_status, "to_status": "closed"},
        ip_address=ip_address,
    )
    db.commit()
    return ticket

