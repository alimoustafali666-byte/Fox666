"""Shared cursor pagination: opaque tokens encoding (created_at, id) of
the last row seen, rather than an OFFSET.

Chosen over limit/offset for any continuously-appended, timestamp-ordered
table (audit_logs, projects, and future Documents/Daily Brief/Tasks
listings alike): with OFFSET, a page fetched while new rows are being
inserted ahead of it silently skips or repeats rows (the Nth row from the
top keeps moving). A cursor anchored to a specific row's (created_at, id)
doesn't have that problem -- and it stays simple because the realistic
access pattern for these listings is "give me the next page older than
the last one I saw", not arbitrary "jump to page N".
"""

import base64
import uuid
from datetime import datetime

_SEPARATOR = "|"


class InvalidCursorError(ValueError):
    pass


def encode_cursor(created_at: datetime, entry_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}{_SEPARATOR}{entry_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_at_str, id_str = raw.split(_SEPARATOR)
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError("Invalid pagination cursor.") from exc

