"""Internal exception hierarchy for the processing pipeline.

Every raise site here constructs its own safe, bounded, human-readable
message -- never a raw parser/vendor exception's text. The orchestrator
(app.modules.documents.processing_orchestrator) is the only place that
catches these and is responsible for translating them into what's
actually persisted to documents.processing_error_code/_message and what
the API returns; nothing below this layer ever reaches an HTTP response
directly.

error_code is a closed, small vocabulary (plain TEXT in the database, no
enum -- same rationale as documents.status: new codes may be added later
without a migration).
"""


class ProcessingError(Exception):
    error_code: str = "processing_failed"


class UnsupportedFileTypeForProcessingError(ProcessingError):
    """No parser is registered for this document's file_type (e.g. an
    image -- PDF/DOCX/XLSX are the only parsers this step implements).
    """

    error_code = "unsupported_file_type"


class InsufficientTextError(ProcessingError):
    """The parser ran successfully but produced no meaningful extractable
    text -- most commonly a scanned/image-only PDF with no native text
    layer. OCR is explicitly out of scope for this step; this is the
    "OCR_REQUIRED-equivalent" signal the step description asks for,
    rather than silently marking such a document processed with zero
    chunks.
    """

    error_code = "insufficient_text"


class PathologicalDocumentError(ProcessingError):
    """A configured structural resource limit was exceeded -- page
    count, sheet count, row/column dimensions, total extracted text
    size, or an oversized zip entry. Always a configuration-driven
    threshold, never a hard-coded one.
    """

    error_code = "resource_limit_exceeded"


class ParserFailureError(ProcessingError):
    """The underlying parser library raised while reading the file --
    a malformed/corrupt document, not a resource-limit or content issue.
    """

    error_code = "parse_failed"


class ProcessingStorageError(ProcessingError):
    """The document's object could not be fetched from StorageProvider."""

    error_code = "storage_unavailable"

