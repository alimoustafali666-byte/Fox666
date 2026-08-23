"""Ask Your Business API (Step 11). Open to all four roles
(owner/admin/manager/member) -- reading/asking against documents a user
is already authorized to read is a read permission every member already
has elsewhere in this API (documents, search); there is no additional
role restriction here. Conversations are creator-private (see
app.modules.conversations.models.Conversation's docstring): every
endpoint below resolves company_id AND created_by from TenantContext --
never from client input.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.service import TenantContext
from app.modules.conversations import ask_service, repository, service
from app.modules.conversations.models import Conversation, Message
from app.modules.conversations.schemas import (
    AskRequest,
    CitationPublic,
    ConversationCreateRequest,
    ConversationPage,
    ConversationPublic,
    MessagePage,
    MessagePublic,
)
from app.modules.documents.models import DOCUMENT_TYPES

router = APIRouter(prefix="/conversations", tags=["conversations"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _conversation_to_public(conversation: Conversation) -> ConversationPublic:
    return ConversationPublic(
        id=conversation.id,
        company_id=conversation.company_id,
        created_by=conversation.created_by,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _citation_to_public(citation: ask_service.CitationSource) -> CitationPublic:
    return CitationPublic(
        document_chunk_id=citation.document_chunk_id,
        document_id=citation.document_id,
        file_name=citation.file_name,
        document_type=citation.document_type,
        project_id=citation.project_id,
        page_number=citation.page_number,
        sheet_name=citation.sheet_name,
        section_name=citation.section_name,
        source_location=citation.source_location,
    )


def _message_to_public(
    message: Message, citations: list[ask_service.CitationSource]
) -> MessagePublic:
    return MessagePublic(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        is_sufficient=message.is_sufficient,
        model_identifier=message.model_identifier,
        created_at=message.created_at,
        citations=[_citation_to_public(c) for c in citations],
    )


@router.post("", response_model=ConversationPublic, status_code=201)
def create_conversation(
    data: ConversationCreateRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.create_conversation(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        title=data.title,
        ip_address=get_client_ip(request),
    )
    return _conversation_to_public(conversation)


@router.get("", response_model=ConversationPage)
def list_conversations(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ConversationPage:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    rows = service.list_conversations(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        limit=limit + 1,
        cursor=decoded_cursor,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more and page_rows else None
    )

    return ConversationPage(
        items=[_conversation_to_public(c) for c in page_rows], next_cursor=next_cursor
    )


@router.get("/{conversation_id}", response_model=ConversationPublic)
def get_conversation(
    conversation_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ConversationPublic:
    conversation = service.get_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )
    return _conversation_to_public(conversation)


@router.get("/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> MessagePage:
    # Resolves (and 404s) via the same creator-private authorization
    # check as every other conversation endpoint before touching messages.
    service.get_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )

    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    rows = repository.list_messages(
        db,
        company_id=context.company_id,
        conversation_id=conversation_id,
        limit=limit + 1,
        cursor=decoded_cursor,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more and page_rows else None
    )

    citations_by_message = ask_service.load_citation_sources_for_messages(
        db, company_id=context.company_id, message_ids=[m.id for m in page_rows]
    )

    return MessagePage(
        items=[
            _message_to_public(m, citations_by_message.get(m.id, [])) for m in page_rows
        ],
        next_cursor=next_cursor,
    )


@router.post("/{conversation_id}/messages", response_model=MessagePublic, status_code=201)
def ask_question(
    conversation_id: uuid.UUID,
    data: AskRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> MessagePublic:
    conversation = service.get_conversation(
        db, company_id=context.company_id, actor_user_id=context.user.id, conversation_id=conversation_id
    )

    if data.document_type is not None and data.document_type not in DOCUMENT_TYPES:
        raise BadRequestError(f"document_type must be one of {sorted(DOCUMENT_TYPES)}.")

    result = ask_service.ask_question(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        conversation=conversation,
        question=data.question,
        document_id=data.document_id,
        project_id=data.project_id,
        document_type=data.document_type,
        ip_address=get_client_ip(request),
    )

    return MessagePublic(
        id=result.message_id,
        conversation_id=result.conversation_id,
        role=result.role,
        content=result.content,
        is_sufficient=result.is_sufficient,
        model_identifier=result.model_identifier,
        created_at=result.created_at,
        citations=[_citation_to_public(c) for c in result.citations],
    )

