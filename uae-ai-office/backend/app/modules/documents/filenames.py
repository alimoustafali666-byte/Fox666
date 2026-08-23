"""Display-only filename sanitization. The result is stored purely as
metadata (Document.file_name) for humans to read -- it is never used to
build the storage key (see app.core.storage.keys.build_document_object_key,
which only ever takes company_id/document_id/a fixed internal object
name) and never interpreted as a filesystem or object-storage path.
"""

import unicodedata

MAX_FILENAME_LENGTH = 255
FALLBACK_FILENAME = "document"


def sanitize_filename(raw: str | None) -> str:
    name = raw or ""

    # Keep only the last path segment. This isn't a traversal defense
    # (nothing downstream ever treats this value as a path), just
    # hygiene: a client-supplied "../../etc/passwd" shouldn't be stored
    # and displayed as if it were a legitimate simple filename.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]

    # Drop C0/C1 control characters and other Unicode control/format
    # characters (e.g. embedded NUL, zero-width space) rather than
    # denylisting specific code points.
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf"))

    name = name.strip().strip(".")
    name = name[:MAX_FILENAME_LENGTH]

    return name or FALLBACK_FILENAME

