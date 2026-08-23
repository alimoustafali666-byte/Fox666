import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    metadata: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    # Opaque -- pass back as ?cursor=... to get the next page. None means
    # this was the last page.
    next_cursor: str | None

