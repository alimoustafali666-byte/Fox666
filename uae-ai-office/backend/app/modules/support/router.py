"""Help & Support API (Step 17). Ticket creation/reply/self-close and
the Support Assistant are open to all four roles -- using the product
and asking for help with it is not a privileged action, same rationale
as Ask Your Business (app.modules.conversations.router). Tickets are
creator-private; see app.modules.support.service and this module's
tests for the authorization/tenant-isolation guarantees.
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
from app.modules.support import assistant_service, kb_search, service
from app.modules.support.articles import ARTICLES, ARTICLES_BY_SLUG, Article
from app.modules.support.models import SUPPORT_TICKET_STATUSES
from app.modules.support.schemas import (
    SupportArticlePage,
    SupportArticlePublic,
    SupportAssistantAskRequest,
    SupportAssistantAskResponse,
    SupportSearchRequest,
    SupportTicketCommentCreate,
    SupportTicketCommentPublic,
    SupportTicketCreate,
    SupportTicketDetail,
    SupportTicketPage,
    SupportTicketPublic,
    SupportTicketStatusUpdate,
)

router = APIRouter(prefix="/support", tags=["support"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
_LOCALES = ("en", "ar")


def _normalize_locale(locale: str) -> str:
    return locale if locale in _LOCALES else "en"


def _article_to_public(article: Article, locale: str) -> SupportArticlePublic:
    locale = _normalize_locale(locale)
    return SupportArticlePublic(
        slug=article.slug,
        category=article.category,
        title=article.title_ar if locale == "ar" else article.title_en,
        body=article.body_ar if locale == "ar" else article.body_en,
    )


def _ticket_to_public(ticket) -> SupportTicketPublic:
    return SupportTicketPublic(
        id=ticket.id,
        company_id=ticket.company_id,
        created_by=ticket.created_by,
        category=ticket.category,
        subject=ticket.subject,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        reference_code=ticket.reference_code,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        resolved_at=ticket.resolved_at,
    )


def _comment_to_public(comment) -> SupportTicketCommentPublic:
    return SupportTicketCommentPublic(
        id=comment.id,
        ticket_id=comment.ticket_id,
        author_type=comment.author_type,
        author_user_id=comment.author_user_id,
        body=comment.body,
        created_at=comment.created_at,
    )


@router.get("/articles", response_model=SupportArticlePage)
def list_articles(
    category: str | None = None,
    locale: str = "en",
    context: TenantContext = Depends(get_tenant_context),
) -> SupportArticlePage:
    articles = kb_search.articles_by_category(category) if category else list(ARTICLES)
    return SupportArticlePage(items=[_article_to_public(a, locale) for a in articles])


@router.get("/articles/{slug}", response_model=SupportArticlePublic)
def get_article(
    slug: str,
    locale: str = "en",
    context: TenantContext = Depends(get_tenant_context),
) -> SupportArticlePublic:
    article = ARTICLES_BY_SLUG.get(slug)
    if article is None:
        raise BadRequestError("Unknown help article.")
    return _article_to_public(article, locale)


@router.post("/search", response_model=SupportArticlePage)
def search_articles(
    data: SupportSearchRequest,
    locale: str = "en",
    context: TenantContext = Depends(get_tenant_context),
) -> SupportArticlePage:
    locale = _normalize_locale(locale)
    results = kb_search.search_articles(data.query, locale=locale, limit=10)
    return SupportArticlePage(items=[_article_to_public(a, locale) for a in results])


@router.post("/assistant/ask", response_model=SupportAssistantAskResponse)
def ask_assistant(
    data: SupportAssistantAskRequest,
    request: Request,
    locale: str = "en",
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportAssistantAskResponse:
    return assistant_service.ask_support_assistant(
        db,
        context=context,
        question=data.question,
        locale=_normalize_locale(locale),
        diagnostics_input=data.diagnostics,
        ip_address=get_client_ip(request),
    )


@router.post("/tickets", response_model=SupportTicketPublic, status_code=201)
def create_ticket(
    data: SupportTicketCreate,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportTicketPublic:
    ticket = service.create_ticket(
        db,
        context=context,
        category=data.category,
        subject=data.subject,
        description=data.description,
        priority=data.priority,
        diagnostics_input=data.diagnostics,
        ip_address=get_client_ip(request),
    )
    return _ticket_to_public(ticket)


@router.get("/tickets", response_model=SupportTicketPage)
def list_tickets(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportTicketPage:
    if status is not None and status not in SUPPORT_TICKET_STATUSES:
        raise BadRequestError(f"status must be one of {sorted(SUPPORT_TICKET_STATUSES)}.")

    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    rows = service.list_tickets(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        limit=limit + 1,
        status=status,
        cursor=decoded_cursor,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id) if has_more and page_rows else None
    )

    return SupportTicketPage(items=[_ticket_to_public(t) for t in page_rows], next_cursor=next_cursor)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail)
def get_ticket(
    ticket_id: uuid.UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportTicketDetail:
    ticket = service.get_ticket(
        db, company_id=context.company_id, actor_user_id=context.user.id, ticket_id=ticket_id
    )
    comments = service.list_comments(db, company_id=context.company_id, ticket_id=ticket.id)
    return SupportTicketDetail(
        **_ticket_to_public(ticket).model_dump(),
        comments=[_comment_to_public(c) for c in comments],
    )


@router.post("/tickets/{ticket_id}/comments", response_model=SupportTicketCommentPublic, status_code=201)
def add_comment(
    ticket_id: uuid.UUID,
    data: SupportTicketCommentCreate,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportTicketCommentPublic:
    comment = service.add_comment(
        db,
        context=context,
        ticket_id=ticket_id,
        body=data.body,
        ip_address=get_client_ip(request),
    )
    return _comment_to_public(comment)


@router.patch("/tickets/{ticket_id}/status", response_model=SupportTicketPublic)
def update_ticket_status(
    ticket_id: uuid.UUID,
    data: SupportTicketStatusUpdate,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SupportTicketPublic:
    ticket = service.update_ticket_status(
        db,
        context=context,
        ticket_id=ticket_id,
        new_status=data.status,
        ip_address=get_client_ip(request),
    )
    return _ticket_to_public(ticket)

