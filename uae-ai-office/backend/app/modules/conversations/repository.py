import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.conversations.models import Conversation, Message, MessageCitation


def create_conversation(
    db: Session, *, id: uuid.UUID, company_id: uuid.UUID, created_by: uuid.UUID, title: str | None
) -> Conversation:
    # created_at is set explicitly in Python, not left to the column's
    # `now()` server_default: Postgres freezes now() to the start of the
    # enclosing transaction, so two rows inserted in the same transaction
    # (as every ask_question() call does for its user+assistant message
    # pair) would otherwise get an IDENTICAL created_at and fall back to
    # an unordered id tiebreak -- silently scrambling message order.
    now = datetime.now(UTC)
    conversation = Conversation(
        id=id, company_id=company_id, created_by=created_by, title=title, created_at=now, updated_at=now
    )
    db.add(conversation)
    db.flush()
    return conversation


def get_conversation_by_id(
    db: Session, *, company_id: uuid.UUID, created_by: uuid.UUID, conversation_id: uuid.UUID
) -> Conversation | None:
    """The `created_by` filter here is defense-in-depth on top of RLS
    (the creator-private tenant_isolation policy on `conversations`
    already makes another user's row physically unreadable in this
    session) -- mirrors how every other repository function in this
    codebase adds an explicit company_id filter on top of RLS.
    """
    return db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.company_id == company_id,
            Conversation.created_by == created_by,
        )
    ).scalar_one_or_none()


def list_conversations(
    db: Session,
    *,
    company_id: uuid.UUID,
    created_by: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[Conversation]:
    query = select(Conversation).where(
        Conversation.company_id == company_id, Conversation.created_by == created_by
    )
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                Conversation.created_at < cursor_created_at,
                and_(Conversation.created_at == cursor_created_at, Conversation.id < cursor_id),
            )
        )
    query = query.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def touch_conversation(db: Session, conversation: Conversation) -> Conversation:
    conversation.updated_at = datetime.now(UTC)
    db.flush()
    return conversation


def create_message(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    is_sufficient: bool | None = None,
    model_identifier: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> Message:
    # See create_conversation's comment: created_at is set explicitly in
    # Python (real wall-clock time, distinct per call) rather than relying
    # on the column's `now()` server_default, which would otherwise be
    # frozen to the same value for a user/assistant pair inserted in the
    # same transaction.
    message = Message(
        id=id,
        company_id=company_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        is_sufficient=is_sufficient,
        model_identifier=model_identifier,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        created_at=datetime.now(UTC),
    )
    db.add(message)
    db.flush()
    return message


def list_messages(
    db: Session,
    *,
    company_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[Message]:
    query = select(Message).where(
        Message.company_id == company_id, Message.conversation_id == conversation_id
    )
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(Message.created_at == cursor_created_at, Message.id < cursor_id),
            )
        )
    query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def list_recent_messages_for_history(
    db: Session, *, company_id: uuid.UUID, conversation_id: uuid.UUID, max_turns: int
) -> list[Message]:
    """Up to `max_turns` most recent user/assistant turn-pairs (i.e. up to
    `2 * max_turns` messages), returned oldest-first -- exactly the
    bounded "limited conversation context" Step 11 requires. Called
    BEFORE the current question's user message is persisted, so it never
    includes the question currently being answered.
    """
    rows = list(
        db.execute(
            select(Message)
            .where(Message.company_id == company_id, Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(max_turns * 2)
        ).scalars()
    )
    rows.reverse()
    return rows


def create_message_citations(
    db: Session,
    *,
    company_id: uuid.UUID,
    message_id: uuid.UUID,
    chunk_ids: list[uuid.UUID],
) -> list[MessageCitation]:
    """`chunk_ids` must already be validated (belongs to this company,
    was actually part of this request's retrieved context, duplicates
    already removed) by the caller -- see ask_service._validate_citations.
    This function trusts that and does not re-validate.
    """
    rows = [
        MessageCitation(
            company_id=company_id,
            message_id=message_id,
            document_chunk_id=chunk_id,
            citation_index=index,
        )
        for index, chunk_id in enumerate(chunk_ids)
    ]
    db.add_all(rows)
    db.flush()
    return rows

