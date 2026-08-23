"""Server-side file-type validation for chat attachments (Step 18) --
extends app.modules.documents.content_validation's exact discipline to a
wider allowlist: PDF, DOCX, XLSX, CSV, TXT, PNG, JPEG, WEBP, plus WEBM/OGG
audio for voice notes (the two container formats produced by browsers'
MediaRecorder API -- Chromium/Edge default to audio/webm;codecs=opus,
Firefox to audio/ogg;codecs=opus).

Same rule as documents: the client-declared filename extension is never
trusted by itself -- it must be consistent with a magic-byte / structural
inspection of the actual bytes. No unsupported "active content" type
(HTML, SVG, archives, macro-enabled Office files, executables/scripts) is
sanitized or partially accepted; anything that doesn't cleanly match one
of the supported types is rejected outright. SVG is deliberately NOT
supported for chat images -- the spec explicitly allows either securely
sanitizing it or disallowing it, and full rejection is the safer,
simpler choice (matches documents' precedent of full rejection over
partial sanitization for anything ambiguous).

CSV/TXT have no magic-byte signature (they are just bytes that happen to
be text), so they are validated differently: the content must decode as
UTF-8 and must not contain a NUL byte in the sampled header -- the
standard heuristic for "this is genuinely text, not binary content
wearing a .txt/.csv extension."
"""

import zipfile
from typing import BinaryIO

from app.modules.collaboration.exceptions import UnsupportedAttachmentTypeError

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_ZIP_MAGIC_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_RIFF_MAGIC = b"RIFF"
_WEBP_MAGIC = b"WEBP"
_EBML_MAGIC = b"\x1a\x45\xdf\xa3"  # WebM/Matroska container header
_OGG_MAGIC = b"OggS"

_EXTENSION_TO_FAMILY = {
    "pdf": "pdf",
    "docx": "docx",
    "xlsx": "xlsx",
    "csv": "csv",
    "txt": "txt",
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "webp": "webp",
    "webm": "webm_audio",
    "ogg": "ogg_audio",
}

CANONICAL_MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "txt": "text/plain",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "webm_audio": "audio/webm",
    "ogg_audio": "audio/ogg",
}

IMAGE_FAMILIES = frozenset({"png", "jpeg", "webp"})
AUDIO_FAMILIES = frozenset({"webm_audio", "ogg_audio"})

_MAX_CONTENT_TYPES_XML_BYTES = 1024 * 1024
_TEXT_SAMPLE_BYTES = 65536


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
    if header.startswith(_RIFF_MAGIC) and header[8:12] == _WEBP_MAGIC:
        return "webp"
    if header.startswith(_EBML_MAGIC):
        return "webm_audio"
    if header.startswith(_OGG_MAGIC):
        return "ogg_audio"
    return None


def _classify_ooxml(fileobj: BinaryIO) -> str | None:
    """Identical logic to documents.content_validation._classify_ooxml --
    only reads zip directory metadata and the small [Content_Types].xml
    member, never extracts document body content, and rejects any
    macro-enabled (VBA) file even if uploaded with a clean extension.
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


def _looks_like_text(fileobj: BinaryIO) -> bool:
    fileobj.seek(0)
    sample = fileobj.read(_TEXT_SAMPLE_BYTES)
    fileobj.seek(0)
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def detect_and_validate_attachment_type(*, filename: str, fileobj: BinaryIO) -> str:
    """Validates that `filename`'s extension is one of the supported chat
    attachment types AND that the actual bytes in `fileobj` structurally
    match that type. Returns the canonical MIME type on success. Leaves
    `fileobj` positioned at offset 0. Raises UnsupportedAttachmentTypeError
    otherwise -- the same generic error whether the extension is
    unsupported or the content doesn't match it, so a rejection never
    discloses which check failed.
    """
    extension = _extract_extension(filename)
    expected_family = _EXTENSION_TO_FAMILY.get(extension)
    if expected_family is None:
        raise UnsupportedAttachmentTypeError(
            "Unsupported file type. Allowed: PDF, DOCX, XLSX, CSV, TXT, PNG, JPG/JPEG, WEBP, WEBM/OGG audio."
        )

    if expected_family in ("csv", "txt"):
        if not _looks_like_text(fileobj):
            raise UnsupportedAttachmentTypeError(
                "The file's content does not match a supported file type."
            )
        return CANONICAL_MIME_TYPES[expected_family]

    fileobj.seek(0)
    header = fileobj.read(16)
    detected_family = _sniff_magic_family(header)

    if detected_family == "zip":
        detected_family = _classify_ooxml(fileobj)

    fileobj.seek(0)

    if detected_family is None or detected_family != expected_family:
        raise UnsupportedAttachmentTypeError(
            "The file's content does not match a supported file type."
        )

    return CANONICAL_MIME_TYPES[expected_family]

