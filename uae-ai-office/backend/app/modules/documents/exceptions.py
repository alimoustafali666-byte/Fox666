from app.core.exceptions import AppError


class DocumentNotFoundError(AppError):
    """Used when a document genuinely doesn't exist, belongs to another
    company, or has been soft-deleted -- deliberately identical in all
    three cases (IDOR protection): a caller must never be able to tell
    "wrong tenant" / "deleted" / "never existed" apart from the response.
    """

    status_code = 404
    code = "document_not_found"


class InvalidDocumentTypeError(AppError):
    status_code = 400
    code = "invalid_document_type"


class UnsupportedFileTypeError(AppError):
    """Covers both an extension outside the supported set and a mismatch
    between the declared extension and the actual detected file content
    -- deliberately not distinguished in the response, so a spoofing
    attempt gets the same generic message as a genuinely unsupported type.
    """

    status_code = 400
    code = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class DocumentStorageUnavailableError(AppError):
    """Generic, safe error for any storage-layer failure reaching the API
    boundary -- upload failure, download-URL generation failure, or a
    DB/storage consistency problem (document row exists but the backing
    object doesn't). Never carries vendor exception text, credentials, or
    the internal storage key.
    """

    status_code = 503
    code = "storage_unavailable"


class DocumentUnsupportedForProcessingError(AppError):
    """No parser is registered for this document's file_type (e.g. an
    image -- PDF/DOCX/XLSX are the only parsers Step 9 implements).
    """

    status_code = 422
    code = "unsupported_file_type_for_processing"


class DocumentInsufficientTextError(AppError):
    """The parser succeeded but found no meaningful extractable text --
    most commonly a scanned/image-only PDF with no native text layer.
    OCR is not implemented yet.
    """

    status_code = 422
    code = "insufficient_text"


class DocumentResourceLimitExceededError(AppError):
    """A configured structural processing limit was exceeded (page/sheet
    count, spreadsheet dimensions, total extracted text, or an oversized
    zip entry) -- the document itself, not a transient failure.
    """

    status_code = 422
    code = "resource_limit_exceeded"


class DocumentParseFailedError(AppError):
    """The document could not be parsed -- a malformed/corrupt file, or
    any other unexpected processing failure. Never carries the
    underlying parser/vendor exception's text.
    """

    status_code = 422
    code = "parse_failed"


class DocumentProcessingUnavailableError(AppError):
    """The document's stored object could not be fetched for processing
    (a StorageProvider failure) -- transient, safe to retry.
    """

    status_code = 503
    code = "processing_unavailable"


class DocumentNotProcessedError(AppError):
    """Indexing was requested for a document whose processing status
    isn't 'processed' yet -- there's no chunk content to embed.
    """

    status_code = 422
    code = "document_not_processed"


class DocumentNoChunksToIndexError(AppError):
    """A processed document with zero chunks (should not normally
    happen -- Step 9's pipeline always produces at least one chunk or
    fails -- but defended against explicitly rather than assumed).
    """

    status_code = 422
    code = "no_chunks_to_index"


class DocumentIndexingFailedError(AppError):
    """Embedding generation failed in a way that isn't a transient
    provider outage -- an unexpected response shape, a vector
    count/dimension mismatch, or any other unexpected failure. Never
    carries the underlying provider exception's text.
    """

    status_code = 422
    code = "indexing_failed"


class DocumentIndexingUnavailableError(AppError):
    """The embedding provider is unavailable or misconfigured (including
    an authentication failure, which is a deployment/credential problem,
    not something the caller can fix by retrying, and is therefore never
    described as an auth failure in the response). Transient from the
    caller's point of view -- safe to retry later.
    """

    status_code = 503
    code = "indexing_unavailable"


class SearchUnavailableError(AppError):
    """The embedding provider could not embed the search query -- the
    same safe, generic treatment as DocumentIndexingUnavailableError,
    under a search-specific name since it isn't about indexing a
    document.
    """

    status_code = 503
    code = "search_unavailable"

