import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.audit_log.service import record_audit_event
from app.modules.conversations import repository
from app.modules.conversations.exceptions import ConversationNotFoundError
from app.modules.conversations.models import Conversation


def create_conversation(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    title: str | None,
    ip_address: str | None,
) -> Conversation:
    conversation = repository.create_conversation(
        db, id=uuid.uuid4(), company_id=company_id, created_by=actor_user_id, title=title
    )
    record_audit_event(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action="conversation.create",
        resource_type="conversation",
        resource_id=conversation.id,
        metadata={"has_title": title is not None},
        ip_address=ip_address,
    )
    db.commit()
    return conversation


def get_conversation(
    db: Session, *, company_id: uuid.UUID, actor_user_id: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation:
    """Creator-private (Step 11 default): another user in the same company
    gets an identical 404 to a genuinely nonexistent or cross-company
    conversation -- see ConversationNotFoundError's docstring. Enforced
    twice: RLS makes another user's row physically unreadable in this
    session, and this repository call adds the same created_by filter
    explicitly as defense-in-depth.
    """
    conversation = repository.get_conversation_by_id(
        db, company_id=company_id, created_by=actor_user_id, conversation_id=conversation_id
    )
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found.")
    return conversation


def list_conversations(
    db: Session,
    *,
    company_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[Conversation]:
    return repository.list_conversations(
        db, company_id=company_id, created_by=actor_user_id, limit=limit, cursor=cursor
    )

