"""Daily Management Brief API (Step 12, on-demand only). Viewing a brief
is open to all four roles (per the approved architecture's RBAC table:
"Ask questions / view brief" -- all four); triggering (re)generation is
owner/admin/manager only ("Trigger brief regeneration" -- member is
excluded). company_id always comes from TenantContext, never client input.
"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.core.request_ip import get_client_ip
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context, require_roles
from app.modules.auth.service import TenantContext
from app.modules.briefs import brief_orchestrator, repository
from app.modules.briefs.exceptions import BriefNotFoundError, InvalidBriefDateError
from app.modules.briefs.models import BriefItem, DailyBrief
from app.modules.briefs.schemas import (
    BriefItemPublic,
    DailyBriefPage,
    DailyBriefPublic,
    DailyBriefSummary,
)

router = APIRouter(prefix="/briefs", tags=["briefs"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _item_to_public(item: BriefItem) -> BriefItemPublic:
    return BriefItemPublic(
        id=item.id, category=item.category, text=item.text, priority=item.priority,
        source_document_id=item.source_document_id,
    )


def _brief_to_public(brief: DailyBrief, items: list[BriefItem]) -> DailyBriefPublic:
    return DailyBriefPublic(
        id=brief.id, company_id=brief.company_id, generated_by=brief.generated_by,
        brief_date=brief.brief_date, summary=brief.summary, generated_at=brief.generated_at,
        items=[_item_to_public(i) for i in items],
    )


def _brief_to_summary(brief: DailyBrief) -> DailyBriefSummary:
    return DailyBriefSummary(
        id=brief.id, company_id=brief.company_id, generated_by=brief.generated_by,
        brief_date=brief.brief_date, summary=brief.summary, generated_at=brief.generated_at,
    )


@router.post("/regenerate", response_model=DailyBriefPublic, status_code=201)
def regenerate_brief(
    request: Request,
    context: TenantContext = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> DailyBriefPublic:
    result = brief_orchestrator.generate_brief(
        db, company_id=context.company_id, actor_user_id=context.user.id,
        ip_address=get_client_ip(request),
    )
    return DailyBriefPublic(
        id=result.brief_id, company_id=result.company_id, generated_by=result.generated_by,
        brief_date=result.brief_date, summary=result.summary, generated_at=result.generated_at,
        items=[_item_to_public(i) for i in result.items],
    )


@router.get("", response_model=DailyBriefPage)
def list_briefs(
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DailyBriefPage:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    rows = repository.list_daily_briefs(
        db, company_id=context.company_id, limit=limit + 1, cursor=decoded_cursor
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].generated_at, page_rows[-1].id) if has_more and page_rows else None
    )

    return DailyBriefPage(items=[_brief_to_summary(b) for b in page_rows], next_cursor=next_cursor)


@router.get("/{brief_date}", response_model=DailyBriefPublic)
def get_brief_by_date(
    brief_date: str,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> DailyBriefPublic:
    """`brief_date` may be a literal ISO date (YYYY-MM-DD) or the literal
    string "latest" for the most recent brief regardless of date.
    """
    if brief_date == "latest":
        brief = repository.get_latest_daily_brief(db, company_id=context.company_id)
    else:
        try:
            parsed_date = date_type.fromisoformat(brief_date)
        except ValueError:
            raise InvalidBriefDateError("brief_date must be an ISO date (YYYY-MM-DD) or 'latest'.") from None
        brief = repository.get_daily_brief_by_date(db, company_id=context.company_id, brief_date=parsed_date)

    if brief is None:
        raise BriefNotFoundError("No brief found for the requested date.")

    items = repository.list_brief_items(db, company_id=context.company_id, brief_id=brief.id)
    return _brief_to_public(brief, items)

