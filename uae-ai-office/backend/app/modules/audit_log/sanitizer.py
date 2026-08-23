"""Defensive metadata sanitizer for audit events.

Deliberately allowlist-by-rejection rather than "trust the caller not to
pass anything sensitive": every audit call in the codebase goes through
this before anything is persisted, so a mistake in ONE call site can't
leak a secret into a durable, admin-readable table.
"""

import re
from typing import Any

_FORBIDDEN_KEY_SUBSTRINGS = (
    "password",
    "passwd",
    "secret",
    "token",
    "jwt",
    "authorization",
    "auth_header",
    "cookie",
    "credential",
    "apikey",
    "api_key",
    "private_key",
    "session_id",
)

# Catches anything shaped like a JWT (three dot-separated base64url
# segments), regardless of which key it was passed under -- a key-only
# blocklist can't catch "a raw access token was accidentally passed as
# the value of an innocuously-named field".
_JWT_SHAPE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

_MAX_STRING_LENGTH = 500
_MAX_KEYS = 20
_MAX_LIST_ITEMS = 20


class UnsafeAuditMetadataError(ValueError):
    """Raised, never silently swallowed by the sanitizer itself, when
    metadata violates the allowlist -- callers decide (per Step 5's
    documented failure policy) whether that aborts the whole operation
    or is handled as best-effort, but the sanitizer's own job is only to
    detect the problem, not to guess what should happen next.
    """


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise UnsafeAuditMetadataError("Audit metadata must be a dict.")
    if len(metadata) > _MAX_KEYS:
        raise UnsafeAuditMetadataError("Audit metadata has too many keys.")

    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise UnsafeAuditMetadataError("Audit metadata keys must be strings.")
        lowered = key.lower()
        if any(bad in lowered for bad in _FORBIDDEN_KEY_SUBSTRINGS):
            raise UnsafeAuditMetadataError(f"Audit metadata key '{key}' is not allowed.")
        cleaned[key] = _sanitize_value(key, value)
    return cleaned


def _sanitize_value(key: str, value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if _JWT_SHAPE.match(value):
            raise UnsafeAuditMetadataError(
                f"Audit metadata value for '{key}' looks like a token and is not allowed."
            )
        if len(value) > _MAX_STRING_LENGTH:
            raise UnsafeAuditMetadataError(f"Audit metadata value for '{key}' is too long.")
        return value
    if isinstance(value, dict):
        return sanitize_metadata(value)
    if isinstance(value, list):
        if len(value) > _MAX_LIST_ITEMS:
            raise UnsafeAuditMetadataError(f"Audit metadata value for '{key}' has too many items.")
        return [_sanitize_value(key, item) for item in value]
    raise UnsafeAuditMetadataError(
        f"Audit metadata value for '{key}' has an unsupported type: {type(value).__name__}."
    )

