"""Server-side file-type validation for document uploads.

The client-declared filename extension is never trusted by itself: it
must be consistent with a magic-byte / structural inspection of the
actual uploaded bytes. Neither signal alone is trusted -- a renamed
executable (wrong content for its claimed extension) and a genuine PDF
uploaded with an unsupported extension are both rejected the same way.

No unsupported "active content" type (HTML, SVG, archives, macro-enabled
Office files) is sanitized or partially accepted; anything that doesn't
cleanly match one of the five supported types is rejected outright.
"""

import zipfile
from typing import BinaryIO

from app.modules.documents.exceptions import UnsupportedFileTypeError

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_ZIP_MAGIC_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

_EXTENSION_TO_FAMILY = {
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "xlsx",
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
}

CANONICAL_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png",
    "jpeg": "image/jpeg",
}


def _extract_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].strip().lower()


def _sniff_magic_family(header: bytes) -> str | None:
    if header.startswith(_PDF_MAGIC):
        return "pdf"
    if header.startswith(_PNG_MAGIC):
        return "png"
    if header.startswith(_JPEG_MAGIC):
        return "jpeg"
    if header.startswith(_ZIP_MAGIC_PREFIXES):
        return "zip"
    return None


# [Content_Types].xml is a small, fixed-purpose manifest -- a real one is
# a few KB at most. A zip entry can declare an arbitrarily small
# compressed size alongside an arbitrarily large *uncompressed* size
# (the classic "zip bomb" shape), so its declared uncompressed size is
# checked before it is ever decompressed, rather than trusting it to be
# small just because it's the only member this code reads.
_MAX_CONTENT_TYPES_XML_BYTES = 1024 * 1024


def _classify_ooxml(fileobj: BinaryIO) -> str | None:
    """`fileobj` must be seekable and already hold the complete (and
    already size-checked) archive. Only reads the zip's directory
    metadata and, for classification, its small [Content_Types].xml
    member -- never extracts or loads the actual document body content.
    Returns None for anything that isn't a clean, non-macro DOCX/XLSX,
    including a genuine DOCM/XLSM (macro-enabled) file even if it was
    uploaded with a .docx/.xlsx extension.
    """
    fileobj.seek(0)
    try:
        with zipfile.ZipFile(fileobj) as zf:
            names = set(zf.namelist())
            if any(name.lower().endswith("vbaproject.bin") for name in names):
                return None
            content_types = ""
            if "[Content_Types].xml" in names:
                info = zf.getinfo("[Content_Types].xml")
                if info.file_size > _MAX_CONTENT_TYPES_XML_BYTES:
                    return None
                content_types = zf.read(info).decode("utf-8", errors="ignore")
    except zipfile.BadZipFile:
        return None

    if "macroenabled" in content_types.lower():
        return None
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    return None


def detect_and_validate_content_type(*, filename: str, fileobj: BinaryIO) -> str:
    """Validates that `filename`'s extension is one of the supported
    types AND that the actual bytes in `fileobj` structurally match that
    type. Returns the canonical MIME type on success. Leaves `fileobj`
    positioned at offset 0. Raises UnsupportedFileTypeError otherwise --
    the same error, with the same generic message, whether the extension
    is simply unsupported or the content doesn't match it.
    """
    extension = _extract_extension(filename)
    expected_family = _EXTENSION_TO_FAMILY.get(extension)
    if expected_family is None:
        raise UnsupportedFileTypeError(
            "Unsupported file type. Allowed: PDF, DOCX, XLSX, PNG, JPG/JPEG."
        )

    fileobj.seek(0)
    header = fileobj.read(8)
    detected_family = _sniff_magic_family(header)

    if detected_family == "zip":
        detected_family = _classify_ooxml(fileobj)

    fileobj.seek(0)

    if detected_family is None or detected_family != expected_family:
        raise UnsupportedFileTypeError(
            "The file's content does not match a supported file type."
        )

    return CANONICAL_MIME_TYPES[expected_family]

