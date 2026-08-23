"""Centralized, safe object-key builder. This is the ONLY place an
object key is ever constructed -- StorageProvider implementations take
an already-built key string and never see a filename or other raw
client input, and callers never assemble a key by hand.

Two independent defenses against path traversal / tenant-namespace
confusion, not just one:

1. company_id and document_id must be real uuid.UUID instances, not
   strings. A malicious string masquerading as an id (e.g.
   "../../other-company") can never reach the f-string at all --
   isinstance() rejects it before any formatting happens. These are
   always server-generated/DB-verified values in practice (never raw
   request input), but the type check makes that a structural
   guarantee rather than a convention to remember.
2. object_name (the only piece ever derived from anything filename-
   adjacent) is validated against a strict allowlist: ASCII letters,
   digits, underscore, hyphen only. No '.', so '..' is categorically
   impossible; no '/' or '\\', so no path separator can appear; no
   non-ASCII, so Unicode normalization/homoglyph tricks can't smuggle a
   separator through. The original filename is never used here at all
   -- it belongs in Postgres as metadata (Step 8), never as a security
   boundary in object storage.
"""

import re
import uuid

from app.core.storage.exceptions import InvalidObjectKeyError

DEFAULT_OBJECT_NAME = "original"
_SAFE_OBJECT_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def build_document_object_key(
    *,
    company_id: uuid.UUID,
    document_id: uuid.UUID,
    object_name: str = DEFAULT_OBJECT_NAME,
) -> str:
    if not isinstance(company_id, uuid.UUID):
        raise InvalidObjectKeyError("company_id must be a UUID.")
    if not isinstance(document_id, uuid.UUID):
        raise InvalidObjectKeyError("document_id must be a UUID.")
    if not isinstance(object_name, str) or not _SAFE_OBJECT_NAME.match(object_name):
        raise InvalidObjectKeyError(
            "object_name must be 1-64 characters of letters, digits, '_' or '-' only."
        )

    return f"companies/{company_id}/documents/{document_id}/{object_name}"


def build_chat_attachment_object_key(
    *,
    company_id: uuid.UUID,
    attachment_id: uuid.UUID,
    object_name: str = DEFAULT_OBJECT_NAME,
) -> str:
    """Same two independent defenses as build_document_object_key above --
    see this module's docstring. A distinct `chat-attachments/` prefix
    keeps Step 18's object namespace unambiguous from Step 8's documents,
    matching the `chat_` table-name prefix chosen for the same reason.
    """
    if not isinstance(company_id, uuid.UUID):
        raise InvalidObjectKeyError("company_id must be a UUID.")
    if not isinstance(attachment_id, uuid.UUID):
        raise InvalidObjectKeyError("attachment_id must be a UUID.")
    if not isinstance(object_name, str) or not _SAFE_OBJECT_NAME.match(object_name):
        raise InvalidObjectKeyError(
            "object_name must be 1-64 characters of letters, digits, '_' or '-' only."
        )

    return f"companies/{company_id}/chat-attachments/{attachment_id}/{object_name}"


def build_company_logo_object_key(*, company_id: uuid.UUID, object_name: str) -> str:
    """Same two independent defenses as build_document_object_key above --
    see this module's docstring. `object_name` here always comes from
    app.modules.tenancy.service's own extension-derived value (e.g.
    "logo.png"), never a client-supplied filename, but it's still run
    through the same allowlist for structural safety -- unlike the other
    two builders, a literal '.' is unavoidable here (an extension is how
    the browser/OS infers image type on download), so the allowlist is
    widened by exactly one character rather than reused verbatim.
    """
    if not isinstance(company_id, uuid.UUID):
        raise InvalidObjectKeyError("company_id must be a UUID.")
    if not isinstance(object_name, str) or not re.match(r"^[a-zA-Z0-9_.-]{1,64}$", object_name):
        raise InvalidObjectKeyError(
            "object_name must be 1-64 characters of letters, digits, '_', '-' or '.' only."
        )
    if ".." in object_name:
        raise InvalidObjectKeyError("object_name must not contain '..'.")

    return f"companies/{company_id}/branding/{object_name}"

