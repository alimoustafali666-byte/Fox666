import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.db.session import get_db
from app.modules.audit_log import repository
from app.modules.audit_log.schemas import AuditLogEntry, AuditLogPage
from app.modules.auth.dependencies import require_roles
from app.modules.auth.service import TenantContext

router = APIRouter(tags=["audit"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@router.get("/audit-logs", response_model=AuditLogPage)
def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    # Audit access is owner/admin only. context.company_id comes from the
    # verified token via get_tenant_context, never from a query/path/body
    # parameter -- there is no way for a caller to ask for another
    # tenant's audit log by supplying a different id anywhere.
    context: TenantContext = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> AuditLogPage:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except InvalidCursorError:
            raise BadRequestError("Invalid pagination cursor.") from None

    rows = repository.list_audit_logs(
        db,
        company_id=context.company_id,
        limit=limit + 1,  # one extra, to know whether there's a next page
        cursor=decoded_cursor,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
    )

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = (
        encode_cursor(page_rows[-1].created_at, page_rows[-1].id)
        if has_more and page_rows
        else None
    )

    return AuditLogPage(
        items=[
            AuditLogEntry(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                metadata=row.metadata_,
                ip_address=row.ip_address,
                created_at=row.created_at,
            )
            for row in page_rows
        ],
        next_cursor=next_cursor,
    )

