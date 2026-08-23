"""DOCX and XLSX are zip archives. python-docx and openpyxl decompress
their internal XML parts with no built-in size cap of their own, so a
crafted entry that declares a tiny compressed size alongside an
enormous *uncompressed* size (the classic zip-bomb shape -- the same
issue found and fixed in Step 8's [Content_Types].xml classification
check) could force one of those libraries to decompress an unbounded
amount of data into memory.

This is checked generically, for every entry in the archive, before
either library ever touches the file -- reading only the zip's central
directory (`ZipInfo.file_size`, the entry's *declared* uncompressed
size), never decompressing anything itself.
"""

import zipfile
from typing import BinaryIO

from app.modules.documents.processing.errors import ParserFailureError, PathologicalDocumentError


def assert_zip_is_safe_to_decompress(
    fileobj: BinaryIO, *, max_entry_bytes: int, max_total_bytes: int
) -> None:
    fileobj.seek(0)
    try:
        with zipfile.ZipFile(fileobj) as zf:
            total = 0
            for info in zf.infolist():
                if info.file_size > max_entry_bytes:
                    raise PathologicalDocumentError(
                        "Document contains a part that is too large to process safely."
                    )
                total += info.file_size
                if total > max_total_bytes:
                    raise PathologicalDocumentError(
                        "Document's total uncompressed content exceeds a safe processing limit."
                    )
    except zipfile.BadZipFile as exc:
        raise ParserFailureError("Document could not be read as a valid file.") from exc
    finally:
        fileobj.seek(0)

