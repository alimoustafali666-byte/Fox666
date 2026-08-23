import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.audit_log.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    company_id: uuid.UUID,
    action: str,
    resource_type: str,
    actor_user_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Raw insert primitive. Internal -- application code should call
    app.modules.audit_log.service.record_audit_event instead, which adds
    metadata sanitization and action-name validation on top of this.
    Caller is responsible for having already set the RLS company context
    to `company_id` (audit_logs is RLS-protected like every other
    tenant-owned table).
    """
    entry = AuditLog(
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry


def list_audit_logs(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[AuditLog]:
    """Relies on audit_logs' tenant_isolation RLS policy: the caller must
    have already set the RLS context to `company_id` (get_tenant_context
    does this). `company_id` is passed explicitly here too as an extra,
    redundant filter -- defense in depth, not the sole isolation
    mechanism: even if this were ever called with the wrong company_id,
    RLS would still only return rows matching the active context.

    Newest first. `cursor`, when given, is the (created_at, id) of the
    last row the caller already saw -- see cursor.py for why this is
    used instead of OFFSET.
    """
    query = select(AuditLog).where(AuditLog.company_id == company_id)

    if action is not None:
        query = query.where(AuditLog.action == action)
    if resource_type is not None:
        query = query.where(AuditLog.resource_type == resource_type)
    if actor_user_id is not None:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if date_from is not None:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.where(AuditLog.created_at <= date_to)
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        query = query.where(
            or_(
                AuditLog.created_at < cursor_created_at,
                and_(
                    AuditLog.created_at == cursor_created_at,
                    AuditLog.id < cursor_id,
                ),
            )
        )

    query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    return list(db.execute(query).scalars())

