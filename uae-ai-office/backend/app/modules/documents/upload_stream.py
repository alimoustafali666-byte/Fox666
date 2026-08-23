"""Bounded, chunked reading of an already-received upload.

FastAPI/Starlette's own multipart parser streams the request body into
UploadFile.file (a SpooledTemporaryFile) in small fixed-size chunks as it
arrives from the network -- it never buffers an entire upload as one
in-memory object, regardless of file size, so memory usage during body
reception is already bounded before any of this module's code runs.

What Starlette does NOT do is enforce our application's own 25MB ceiling
against the actual bytes received (only against a client-supplied
Content-Length, which is not trustworthy on its own). This module makes
one additional bounded, chunked pass over the already-spooled file to
measure its real size and compute its SHA-256 checksum together, reading
fixed-size chunks rather than the whole file, and aborting as soon as the
running total exceeds the configured maximum rather than reading to EOF
first.
"""

import hashlib
from typing import BinaryIO

from app.modules.documents.exceptions import FileTooLargeError

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


def measure_and_checksum(fileobj: BinaryIO, *, max_bytes: int) -> tuple[int, str]:
    """Returns (size_in_bytes, sha256_hex). Leaves `fileobj` positioned
    at EOF; callers that need to read it again (content-type sniffing,
    the actual storage upload) must seek(0) first.

    Raises FileTooLargeError the moment the running total exceeds
    max_bytes -- independent of whatever Content-Length the client
    declared for the request.
    """
    fileobj.seek(0)
    hasher = hashlib.sha256()
    total = 0

    while True:
        chunk = fileobj.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(
                f"File exceeds the maximum allowed size of {max_bytes} bytes."
            )
        hasher.update(chunk)

    return total, hasher.hexdigest()

