"""The one place application code should call to write an audit event.

Every future tenant-owned module (Projects, Documents, team management,
AI features) should call record_audit_event rather than inserting into
audit_logs directly -- this is what actually enforces the sanitization
and naming convention; a scattered set of direct repository.write_audit_log
calls would only be as safe as the least careful call site.
"""

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit_log import repository
from app.modules.audit_log.models import AuditLog
from app.modules.audit_log.sanitizer import sanitize_metadata

# <module>.<action>, both snake_case. Examples: auth.login_success,
# project.create, document.download, membership.role_change. Enforced as
# a format, not a fixed registry -- new modules are free to add new
# action strings as long as they follow the convention.
_ACTION_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class InvalidAuditActionError(ValueError):
    """Action name doesn't follow the <module>.<action> convention. This
    is a programming error (every caller is our own code, never end-user
    input), so it's intentionally not mapped to an HTTP error type.
    """


def record_audit_event(
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
    """Sanitizes metadata, validates the action-name convention, and
    inserts the audit row. Caller must have already set the RLS company
    context to `company_id` (same requirement as the repository layer).

    Failure behavior is the caller's responsibility, not this function's:
    this simply raises (UnsafeAuditMetadataError, InvalidAuditActionError,
    or a database error) rather than silently dropping anything. For a
    state-changing operation, let the exception propagate so the whole
    transaction rolls back -- an operation must never appear to succeed
    while its audit trail silently failed to record. Authentication
    *failure* logging is the one documented exception with different
    transaction constraints; see app.modules.auth.service for where and
    why that call is wrapped differently.
    """
    if not _ACTION_NAME_PATTERN.match(action):
        raise InvalidAuditActionError(
            f"Audit action '{action}' does not follow the '<module>.<action>' convention."
        )

    clean_metadata = sanitize_metadata(metadata)

    return repository.write_audit_log(
        db,
        company_id=company_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=clean_metadata,
        ip_address=ip_address,
    )

